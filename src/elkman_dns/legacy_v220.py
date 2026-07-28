#!/usr/bin/env python3
from __future__ import annotations

import argparse
import configparser
import datetime as dt
import json
import re
import tempfile
import os
import shutil
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

VERSION = "2.2.0"
DEFAULT_CONFIG = Path("/etc/elkman-dns-toolkit/toolkit.conf")
DEFAULT_ZONES = Path("/etc/elkman-dns-toolkit/zones.conf")
GREEN='\033[32m'; RED='\033[31m'; YELLOW='\033[33m'; BOLD='\033[1m'; RESET='\033[0m'

def c(text, code, enabled=True): return f"{code}{text}{RESET}" if enabled else text

def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    except FileNotFoundError: raise RuntimeError(f"Nie znaleziono polecenia: {cmd[0]}")
    except subprocess.TimeoutExpired: raise RuntimeError(f"Przekroczono limit czasu: {' '.join(cmd)}")

def yes(value, default=False):
    if value is None: return default
    value=str(value).strip().lower()
    if value in {'1','yes','true','on','tak'}: return True
    if value in {'0','no','false','off','nie'}: return False
    return default

def require_root(name):
    if os.geteuid()!=0: raise RuntimeError(f"Polecenie '{name}' wymaga uprawnień root.")

def load_config(config_path,zones_path):
    cfg=configparser.ConfigParser(); zones=configparser.ConfigParser()
    if not config_path.exists(): raise RuntimeError(f"Brak pliku: {config_path}")
    if not zones_path.exists(): raise RuntimeError(f"Brak pliku: {zones_path}")
    cfg.read(config_path); zones.read(zones_path)
    if 'toolkit' not in cfg: raise RuntimeError('Brak sekcji [toolkit]')
    return cfg,zones

def zone_items(zones):
    for zone in sorted(zones.sections(), key=str.lower):
        item=zones[zone]
        if yes(item.get('enabled','yes'),True): yield zone,item

def sync_zone_items(zones):
    for zone,item in zone_items(zones):
        if yes(item.get('sync','yes'),True): yield zone,item

def selected(zones,requested):
    available=[z for z,_ in zone_items(zones)]
    if not requested: return available
    missing=[z for z in requested if z not in available]
    if missing: raise RuntimeError('Nieznane strefy: '+', '.join(missing))
    return requested

def dig_lines(server,name,rtype,timeout=3,dnssec=False):
    cmd=['dig',f'@{server}',name,rtype,'+short',f'+time={timeout}','+tries=1']
    if dnssec: cmd.append('+dnssec')
    r=run(cmd,timeout+3)
    return [x.strip() for x in r.stdout.splitlines() if x.strip()] if r.returncode==0 else []

def dig_serial(server,zone,timeout):
    out=dig_lines(server,zone,'SOA',timeout)
    if not out: return None
    p=out[0].split(); return p[2] if len(p)>=3 else None

def authoritative_servers(zone,timeout=3): return [x.rstrip('.') for x in dig_lines('1.1.1.1',zone,'NS',timeout)]
def parent_ds(zone,timeout=3): return dig_lines('1.1.1.1',zone,'DS',timeout,True)
def local_dnskeys(server,zone,timeout=3): return dig_lines(server,zone,'DNSKEY',timeout,True)

def has_rrsig(server,zone,rtype='A',timeout=3):
    r=run(['dig',f'@{server}',zone,rtype,'+dnssec','+noall','+answer',f'+time={timeout}','+tries=1'],timeout+3)
    if r.returncode != 0:
        return False
    wanted = rtype.upper()
    for line in r.stdout.splitlines():
        fields=line.split()
        if 'RRSIG' in fields:
            idx=fields.index('RRSIG')
            if len(fields)>idx+1 and fields[idx+1].upper()==wanted:
                return True
    return False

def delv_validate(zone,server=None,timeout=15):
    cmd=['delv']
    if server:
        cmd.append(f'@{server}')
    cmd.append(zone)
    r=run(cmd,timeout)
    text=((r.stdout or '')+(r.stderr or '')).strip()
    return r.returncode==0,text


def validation_targets(cfg):
    """Zwróć walidatory DNSSEC używane do ustalenia wyniku konsensusu.

    Konfiguracja opcjonalna w [toolkit]:
      dnssec_validators = 1.1.1.1, 8.8.8.8, 9.9.9.9
      dnssec_validation_quorum = 2
    """
    t=cfg['toolkit']
    raw=t.get('dnssec_validators','1.1.1.1,8.8.8.8,9.9.9.9')
    servers=[x.strip() for x in raw.split(',') if x.strip()]
    names={'1.1.1.1':'Cloudflare','8.8.8.8':'Google','9.9.9.9':'Quad9','208.67.222.222':'OpenDNS'}
    return [(names.get(server,server),server) for server in servers]


def dnssec_validation_consensus(cfg,zone,timeout=15):
    local_ok,local_text=delv_validate(zone,None,timeout)
    results={'local':{'server':None,'ok':local_ok,'output':local_text}}
    public=[]
    for label,server in validation_targets(cfg):
        ok,text=delv_validate(zone,server,timeout)
        entry={'server':server,'ok':ok,'output':text}
        results[label]=entry
        public.append(entry)
    quorum=max(2,int(cfg['toolkit'].get('dnssec_validation_quorum','2')))
    successful=sum(1 for x in public if x['ok'])
    consensus=successful>=quorum
    return {
        'ok':consensus,
        'quorum':quorum,
        'successful':successful,
        'total':len(public),
        'local_ok':local_ok,
        'results':results,
        'warning':consensus and not local_ok,
    }

def cmd_check(cfg,zones,args):
    print(c('elkman DNS Toolkit — kontrola konfiguracji',BOLD,not args.no_color))
    r=run(['named-checkconf'])
    if r.returncode!=0:
        print(c('FAIL named-checkconf',RED,not args.no_color)); print((r.stdout+r.stderr).strip()); return 1
    print(c('OK   named-checkconf',GREEN,not args.no_color)); failures=0
    for zone,item in zone_items(zones):
        path=item.get('file','').strip()
        if not path or not Path(path).exists():
            print(c(f'FAIL {zone:<28} brak pliku {path}',RED,not args.no_color)); failures+=1; continue
        r=run(['named-checkzone',zone,path])
        if r.returncode==0: print(c(f'OK   {zone:<28} {path}',GREEN,not args.no_color))
        else:
            failures+=1; print(c(f'FAIL {zone:<28} {path}',RED,not args.no_color)); print((r.stdout+r.stderr).strip())
    return 1 if failures else 0

def cmd_sync(cfg,zones,args):
    t=cfg['toolkit']; local=t.get('local_server','127.0.0.1'); dns2=t.get('dns2_server','5.172.189.198'); he=t.get('he_server','216.218.133.2'); timeout=int(t.get('dig_timeout','3'))
    rows=[]; failures=0
    for zone,item in sync_zone_items(zones):
        cd=yes(item.get('dns2','yes'),True); ch=yes(item.get('he','no'),False)
        ls=dig_serial(local,zone,timeout); ds=dig_serial(dns2,zone,timeout) if cd else None; hs=dig_serial(he,zone,timeout) if ch else None
        problems=[]
        if ls is None: problems.append('brak LOCAL')
        if cd and ds is None: problems.append('brak DNS2')
        elif cd and ls and ds!=ls: problems.append('DNS2 inny serial')
        if ch and hs is None: problems.append('brak HE')
        elif ch and ls and hs!=ls: problems.append('HE inny serial')
        ok=not problems; failures+=0 if ok else 1
        rows.append((zone,ls or 'BRAK',ds if cd and ds else ('BRAK' if cd else '-'),hs if ch and hs else ('BRAK' if ch else '-'),'OK' if ok else '; '.join(problems)))
    print(c('elkman DNS Toolkit — synchronizacja SOA',BOLD,not args.no_color))
    if not rows: print(c('Brak stref przeznaczonych do synchronizacji.',YELLOW,not args.no_color)); return 0
    headers=('STREFA','LOCAL','DNS2','HE','STATUS'); widths=[max(len(headers[i]),max(len(str(r[i])) for r in rows)) for i in range(5)]
    print('  '.join(headers[i].ljust(widths[i]) for i in range(5))); print('  '.join('-'*w for w in widths))
    for row in rows:
        line='  '.join(str(row[i]).ljust(widths[i]) for i in range(5)); print(c(line,GREEN if row[4]=='OK' else RED,not args.no_color))
    return 1 if failures else 0

def cmd_notify(cfg,zones,args):
    require_root('notify'); failures=0
    for zone in selected(zones,args.zones):
        if not yes(zones[zone].get('notify','yes'),True): print(c(f'SKIP NOTIFY {zone}',YELLOW,not args.no_color)); continue
        r=run(['rndc','notify',zone])
        if r.returncode==0: print(c(f'OK   NOTIFY {zone}',GREEN,not args.no_color))
        else: failures+=1; print(c(f'FAIL NOTIFY {zone}: {r.stderr.strip() or r.stdout.strip() or "nieznany błąd"}',RED,not args.no_color))
    return 1 if failures else 0

def cmd_reload(cfg,zones,args):
    require_root('reload')
    if not args.skip_check and cmd_check(cfg,zones,argparse.Namespace(no_color=args.no_color))!=0: return 1
    failures=0; targets=selected(zones,args.zones)
    for zone in targets:
        if not yes(zones[zone].get('reload','yes'),True): print(c(f'SKIP RELOAD {zone}',YELLOW,not args.no_color)); continue
        r=run(['rndc','reload',zone])
        if r.returncode==0: print(c(f'OK   RELOAD {zone}',GREEN,not args.no_color))
        else: failures+=1; print(c(f'FAIL RELOAD {zone}: {r.stderr.strip() or r.stdout.strip()}',RED,not args.no_color))
    if failures==0 and not args.no_notify: failures+=cmd_notify(cfg,zones,argparse.Namespace(zones=targets,no_color=args.no_color))
    return 1 if failures else 0

def cmd_backup(cfg,zones,args):
    require_root('backup'); t=cfg['toolkit']; backup_dir=Path(t.get('backup_dir','/var/backups/elkman-dns')); bind_dir=Path(t.get('bind_dir','/etc/bind'))
    if not bind_dir.exists(): raise RuntimeError(f'Nie istnieje katalog BIND: {bind_dir}')
    backup_dir.mkdir(parents=True,exist_ok=True); dest=backup_dir/f"bind-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz"
    with tarfile.open(dest,'w:gz') as tar:
        tar.add(bind_dir,arcname='etc/bind')
        if DEFAULT_CONFIG.parent.exists(): tar.add(DEFAULT_CONFIG.parent,arcname='etc/elkman-dns-toolkit')
        key_dir=Path(t.get('dnssec_key_directory','/var/lib/bind/keys'))
        if key_dir.exists(): tar.add(key_dir,arcname='var/lib/bind/keys')
        zone_dir=Path(t.get('dnssec_zone_directory','/var/lib/bind/Primary'))
        if zone_dir.exists(): tar.add(zone_dir,arcname='var/lib/bind/Primary')
    print(c(f'OK   Backup: {dest}',GREEN,not args.no_color)); keep=int(t.get('backup_keep','30'))
    for old in sorted(backup_dir.glob('bind-*.tar.gz'),key=lambda p:p.stat().st_mtime,reverse=True)[keep:]: old.unlink(missing_ok=True)
    return 0

def dnssec_zone_result(cfg,zones,zone):
    t=cfg['toolkit']; item=zones[zone]; server=t.get('local_server','127.0.0.1'); timeout=int(t.get('dig_timeout','3'))
    sr=run(['rndc','dnssec','-status',zone]); st=(sr.stdout+sr.stderr).strip(); secure='zone signing:' in st and 'yes' in st
    keys=local_dnskeys(server,zone,timeout); ds=parent_ds(zone,timeout); rrsig=has_rrsig(server,zone,'SOA',timeout)
    validation=dnssec_validation_consensus(cfg,zone,max(15,timeout+5))
    auth={}
    for ns in authoritative_servers(zone,timeout): auth[ns]={'dnskey':bool(local_dnskeys(ns,zone,timeout)),'rrsig':has_rrsig(ns,zone,'SOA',timeout)}
    return {
        'zone':zone,
        'configured':yes(item.get('dnssec','no'),False),
        'rndc_status_ok':sr.returncode==0,
        'secure':secure,
        'dnskey':bool(keys),
        'ds':bool(ds),
        'rrsig':rrsig,
        'validated':validation['ok'],
        'validation':validation,
        'rndc_status':st,
        'delv':validation['results']['local']['output'],
        'authoritative':auth,
    }

def cmd_dnssec_status(cfg,zones,args):
    failures=0
    for zone in selected(zones,args.zones):
        r=dnssec_zone_result(cfg,zones,zone); print(c(zone,BOLD,not args.no_color)); checks=[('configured',r['configured']),('secure',r['secure']),('DNSKEY',r['dnskey']),('DS',r['ds']),('RRSIG',r['rrsig']),('validation',r['validated'])]
        for n,ok in checks: print('  '+c(f'{n:<12} {"OK" if ok else "FAIL"}',GREEN if ok else RED,not args.no_color))
        if r['validation']['warning']:
            print('  '+c('warning      lokalny resolver jeszcze nie waliduje; konsensus zewnętrzny jest OK',YELLOW,not args.no_color))
        failures+=0 if all(ok for _,ok in checks) else 1
        if args.verbose:
            print(r['rndc_status'])
            print(f"Walidacja zewnętrzna: {r['validation']['successful']}/{r['validation']['total']} (quorum {r['validation']['quorum']})")
            for label,vr in r['validation']['results'].items():
                print(f"  {label:<12} {'OK' if vr['ok'] else 'FAIL'}" + (f" @{vr['server']}" if vr['server'] else ''))
    return 1 if failures else 0

def explain_dnssec_result(r,no_color=False):
    print()
    print(c('WYJAŚNIENIE',BOLD,not no_color))
    v=r['validation']
    for label,vr in v['results'].items():
        endpoint=f" @{vr['server']}" if vr['server'] else ''
        print('  '+c(f'{label:<12} {"OK" if vr["ok"] else "FAIL"}{endpoint}',GREEN if vr['ok'] else YELLOW,not no_color))
    print(f"  Konsensus: {v['successful']}/{v['total']} zewnętrznych walidatorów; wymagane quorum: {v['quorum']}.")
    problems=[]
    if not r['rndc_status_ok']: problems.append('BIND nie zwrócił poprawnego statusu KASP.')
    if not r['secure']: problems.append('Strefa nie jest aktywnie podpisywana.')
    if not r['dnskey']: problems.append('Brak DNSKEY na serwerze lokalnym.')
    if not r['ds']: problems.append('Brak DS w strefie nadrzędnej lub rekord nie jest jeszcze widoczny publicznie.')
    if not r['rrsig']: problems.append('Brak RRSIG dla SOA na serwerze lokalnym.')
    bad_auth=[ns for ns,x in r['authoritative'].items() if not (x['dnskey'] and x['rrsig'])]
    if bad_auth: problems.append('Nie wszystkie serwery autorytatywne publikują DNSKEY i RRSIG: '+', '.join(bad_auth)+'.')
    if not v['ok']:
        problems.append('Za mało niezależnych resolverów potwierdza pełny łańcuch zaufania DNSSEC.')
    if problems:
        print(c('  Diagnoza:',YELLOW,not no_color))
        for problem in problems: print('   - '+problem)
    elif v['warning']:
        print(c('  Diagnoza: DNSSEC jest wdrożony poprawnie. Tylko lokalny resolver ma nieaktualny cache lub inną ścieżkę walidacji.',YELLOW,not no_color))
        print('  Zalecenie: rndc flushname '+r['zone']+' && rndc flushname '+'.'.join(r['zone'].split('.')[1:]))
    else:
        print(c('  Diagnoza: pełny łańcuch zaufania DNSSEC działa poprawnie lokalnie i na niezależnych resolverach.',GREEN,not no_color))


def cmd_dnssec_check(cfg,zones,args):
    failures=0
    for zone in selected(zones,args.zones):
        r=dnssec_zone_result(cfg,zones,zone); print(c(f'DNSSEC CHECK — {zone}',BOLD,not args.no_color))
        validation_label=f"pełna walidacja — konsensus {r['validation']['successful']}/{r['validation']['total']} (quorum {r['validation']['quorum']})"
        core=[('KASP/rndc',r['rndc_status_ok']),('podpisywanie strefy',r['secure']),('DNSKEY lokalnie',r['dnskey']),('DS w strefie nadrzędnej',r['ds']),('RRSIG SOA',r['rrsig']),(validation_label,r['validated'])]
        ok_all=True; warnings=False
        for label,ok in core: ok_all&=ok; print('  '+c(f'{"OK" if ok else "FAIL":<4} {label}',GREEN if ok else RED,not args.no_color))
        for label,vr in r['validation']['results'].items():
            endpoint=f" @{vr['server']}" if vr['server'] else ''
            if label=='local' and not vr['ok'] and r['validated']:
                warnings=True; state='WARN'; color=YELLOW
            else:
                state='OK' if vr['ok'] else 'FAIL'; color=GREEN if vr['ok'] else RED
            print('  '+c(f'{state:<4} walidator {label}{endpoint}',color,not args.no_color))
        for ns,nr in r['authoritative'].items():
            ok=nr['dnskey'] and nr['rrsig']; ok_all&=ok; print('  '+c(f'{"OK" if ok else "FAIL":<4} {ns}: DNSKEY={"OK" if nr["dnskey"] else "BRAK"}, RRSIG={"OK" if nr["rrsig"] else "BRAK"}',GREEN if ok else RED,not args.no_color))
        if ok_all and warnings:
            print(c('RESULT: PASS WITH WARNINGS',YELLOW,not args.no_color))
        else:
            print(c('RESULT: PASS' if ok_all else 'RESULT: FAIL',GREEN if ok_all else RED,not args.no_color))
        if getattr(args,'explain',False): explain_dnssec_result(r,args.no_color)
        failures+=0 if ok_all else 1
    return 1 if failures else 0

def cmd_dnssec_report(cfg,zones,args):
    results=[dnssec_zone_result(cfg,zones,z) for z in selected(zones,args.zones)]
    if args.json: print(json.dumps(results,indent=2,ensure_ascii=False)); return 0 if all(r['validated'] for r in results) else 1
    failures=0
    for r in results:
        healthy=all([r['configured'],r['secure'],r['dnskey'],r['ds'],r['rrsig'],r['validated']]); failures+=0 if healthy else 1
        print(f"DNSSEC REPORT — {r['zone']}\n"+'='*(17+len(r['zone']))); print(f"Configured ........ {'YES' if r['configured'] else 'NO'}\nSigned ............ {'YES' if r['secure'] else 'NO'}\nDNSKEY ............ {'PRESENT' if r['dnskey'] else 'MISSING'}\nDS parent ......... {'PRESENT' if r['ds'] else 'MISSING'}\nRRSIG ............. {'PRESENT' if r['rrsig'] else 'MISSING'}\nValidation ........ {'OK' if r['validated'] else 'FAIL'}\nStatus ............ {'HEALTHY' if healthy else 'PROBLEM'}\n")
    return 1 if failures else 0

def cmd_health(cfg,zones,args):
    t=cfg['toolkit']; server=t.get('local_server','127.0.0.1'); timeout=int(t.get('dig_timeout','3')); failures=0
    requested=set(getattr(args,'zones',[]) or [])
    for zone,item in zone_items(zones):
        if requested and zone not in requested: continue
        if not yes(item.get('health','yes'),True) or yes(item.get('reverse','no'),False) or yes(item.get('internal','no'),False): continue
        txt=dig_lines(server,zone,'TXT',timeout); dm=dig_lines(server,'_dmarc.'+zone,'TXT',timeout)
        checks=[('SOA',bool(dig_lines(server,zone,'SOA',timeout))),('NS',bool(dig_lines(server,zone,'NS',timeout))),('MX',bool(dig_lines(server,zone,'MX',timeout))),('SPF',any('v=spf1' in x.lower() for x in txt)),('DMARC',any('v=dmarc1' in x.lower() for x in dm)),('CAA',bool(dig_lines(server,zone,'CAA',timeout)))]
        if yes(item.get('dnssec','no'),False):
            r=dnssec_zone_result(cfg,zones,zone); checks += [('DNSKEY',r['dnskey']),('DS',r['ds']),('RRSIG',r['rrsig']),('DNSSEC',r['validated'])]
        if not all(v for _,v in checks): failures+=1
        print(c(zone,BOLD,not args.no_color)); print('  '+'  '.join(f'{n}={"OK" if v else "BRAK"}' for n,v in checks))
    return 1 if failures else 0

def cmd_doctor(cfg,zones,args):
    tests=[]
    def add(name,ok,detail=''): tests.append((name,ok,detail))
    for command in ('named-checkconf','named-checkzone','rndc','dig','delv'): add(f'polecenie {command}',shutil.which(command) is not None)
    r=run(['named-checkconf']); add('named-checkconf',r.returncode==0,(r.stdout+r.stderr).strip())
    r=run(['systemctl','is-active','named']); add('usługa named',r.returncode==0,r.stdout.strip())
    app=Path('/sys/module/apparmor/parameters/enabled'); add('AppArmor',not app.exists() or app.read_text(errors='ignore').strip().upper().startswith('Y'),'aktywny' if app.exists() else 'brak modułu')
    key_dir=Path(cfg['toolkit'].get('dnssec_key_directory','/var/lib/bind/keys')); add('katalog kluczy DNSSEC',key_dir.exists(),str(key_dir));
    if key_dir.exists(): add('zapis katalogu kluczy',os.access(key_dir,os.W_OK),str(key_dir))
    for zone,item in zone_items(zones):
        path=Path(item.get('file','')); add(f'{zone}: plik strefy',path.exists(),str(path))
        if path.exists():
            r=run(['named-checkzone',zone,str(path)]); add(f'{zone}: named-checkzone',r.returncode==0,(r.stdout+r.stderr).strip())
            if yes(item.get('dnssec','no'),False): add(f'{zone}: lokalizacja inline-signing',not str(path).startswith('/etc/bind/'),str(path) if not str(path).startswith('/etc/bind/') else 'zalecane /var/lib/bind/Primary')
    passed=sum(1 for _,ok,_ in tests if ok); failed=len(tests)-passed
    for name,ok,detail in tests:
        line=f'{"OK" if ok else "FAIL":<4} {name}' + (f' — {detail}' if detail and (args.verbose or not ok) else '')
        print(c(line,GREEN if ok else RED,not args.no_color))
    print(); print(c(f'✔ {passed} tests passed',GREEN,not args.no_color)); print(c(f'✖ {failed} tests failed',RED,not args.no_color) if failed else c('No problems detected.',GREEN,not args.no_color)); return 1 if failed else 0


def confirm(question, default=False):
    suffix=' [T/n] ' if default else ' [t/N] '
    answer=input(question+suffix).strip().lower()
    if not answer:
        return default
    return answer in {'t','tak','y','yes'}


def update_ini_zone(zones_path, zone, new_path=None, dnssec=None):
    text=zones_path.read_text()
    header=re.compile(r'^\s*\['+re.escape(zone)+r'\]\s*$',re.M)
    m=header.search(text)
    if not m:
        raise RuntimeError(f'Brak sekcji [{zone}] w {zones_path}')
    next_header=re.search(r'^\s*\[[^]]+\]\s*$',text[m.end():],re.M)
    end=m.end()+(next_header.start() if next_header else len(text)-m.end())
    block=text[m.end():end]
    def set_option(block,key,value):
        pattern=re.compile(r'^(\s*'+re.escape(key)+r'\s*=\s*).*$' ,re.M|re.I)
        if pattern.search(block):
            return pattern.sub(lambda mm:mm.group(1)+value,block,count=1)
        sep='' if block.endswith('\n') else '\n'
        return block+sep+f'{key} = {value}\n'
    if new_path is not None:
        block=set_option(block,'file',str(new_path))
    if dnssec is not None:
        block=set_option(block,'dnssec','yes' if dnssec else 'no')
    tmp=zones_path.with_suffix(zones_path.suffix+'.tmp')
    tmp.write_text(text[:m.end()]+block+text[end:])
    os.replace(tmp,zones_path)


def find_zone_config(zone, bind_dir=Path('/etc/bind')):
    """Znajdź aktywny plik zawierający deklarację zone.

    Nie ograniczamy wyszukiwania do ``*.conf``, ponieważ typowy plik BIND
    ``named.conf.local`` nie pasuje do tego wzorca. Pomijamy kopie zapasowe
    i pliki robocze, aby nie wykrywać tej samej strefy wielokrotnie.
    """
    zone_re=re.compile(r'\bzone\s+["\']'+re.escape(zone)+r'["\']\s*\{',re.I)
    candidates=[]
    skip_suffixes=('.jnl','.signed','.signed.jnl','.tmp','.swp','.swo','~')
    skip_markers=('.bak-','.bak.','.dpkg-old','.dpkg-dist','.ucf-old')

    for path in bind_dir.rglob('*'):
        if not path.is_file():
            continue
        name=path.name.lower()
        if name.endswith(skip_suffixes) or any(marker in name for marker in skip_markers) or name.endswith('.bak'):
            continue
        try:
            if path.stat().st_size > 10 * 1024 * 1024:
                continue
            text=path.read_text(errors='ignore')
        except OSError:
            continue
        m=zone_re.search(text)
        if m:
            candidates.append((path,text,m.start()))

    if not candidates:
        raise RuntimeError(f'Nie znaleziono deklaracji zone "{zone}" w {bind_dir}')
    if len(candidates)>1:
        raise RuntimeError('Znaleziono kilka aktywnych deklaracji strefy: '+', '.join(str(x[0]) for x in candidates))
    return candidates[0]


def zone_block_bounds(text,start):
    opening=text.find('{',start)
    if opening<0: raise RuntimeError('Nie znaleziono początku bloku zone')
    depth=0; quote=None; escaped=False
    for i in range(opening,len(text)):
        ch=text[i]
        if quote:
            if escaped: escaped=False
            elif ch=='\\': escaped=True
            elif ch==quote: quote=None
            continue
        if ch in {'"', "'"}: quote=ch
        elif ch=='{': depth+=1
        elif ch=='}':
            depth-=1
            if depth==0: return opening,i
    raise RuntimeError('Nie znaleziono końca bloku zone')


def patch_zone_declaration(path,text,start,old_file,new_file,key_dir):
    opening,closing=zone_block_bounds(text,start)
    block=text[opening+1:closing]
    file_re=re.compile(r'(^\s*file\s+)["\'][^"\']+["\'](\s*;)',re.M|re.I)
    if file_re.search(block):
        block=file_re.sub(lambda m: m.group(1)+'"'+str(new_file)+'"'+m.group(2),block,count=1)
    else:
        block+='\n        file "'+str(new_file)+'";'
    additions=[]
    if not re.search(r'\bdnssec-policy\s+',block,re.I): additions.append('        dnssec-policy default;')
    if not re.search(r'\binline-signing\s+',block,re.I): additions.append('        inline-signing yes;')
    if not re.search(r'\bkey-directory\s+',block,re.I): additions.append(f'        key-directory "{key_dir}";')
    if additions: block+='\n'+'\n'.join(additions)+'\n'
    patched=text[:opening+1]+block+text[closing:]
    path.write_text(patched)


def generate_ds(server,zone,timeout=5):
    r=run(['dig',f'@{server}',zone,'DNSKEY','+dnssec','+noall','+answer',f'+time={timeout}','+tries=1'],timeout+3)
    if r.returncode!=0 or 'DNSKEY' not in r.stdout:
        return []
    tool=shutil.which('dnssec-dsfromkey')
    if not tool:
        raise RuntimeError('Brak dnssec-dsfromkey (pakiet bind9-utils).')
    with tempfile.NamedTemporaryFile('w',delete=False) as fh:
        fh.write(r.stdout); name=fh.name
    try:
        d=run([tool,'-2','-f',name,zone],10)
        if d.returncode!=0:
            raise RuntimeError((d.stderr or d.stdout).strip())
        return [x.strip() for x in d.stdout.splitlines() if x.strip() and ' IN DS ' in x]
    finally:
        Path(name).unlink(missing_ok=True)


def cmd_dnssec_enable(cfg,zones,args):
    require_root('dnssec-enable')
    zone=args.zone
    if zone not in zones or not yes(zones[zone].get('enabled','yes'),True):
        raise RuntimeError(f'Nieznana lub wyłączona strefa: {zone}')
    item=zones[zone]; t=cfg['toolkit']; no_color=args.no_color
    old_path=Path(item.get('file','')).resolve()
    if not old_path.exists(): raise RuntimeError(f'Brak pliku strefy: {old_path}')
    key_dir=Path(t.get('dnssec_key_directory','/var/lib/bind/keys'))
    target_dir=Path(t.get('dnssec_zone_directory','/var/lib/bind/Primary'))
    target_path=old_path
    print(c(f'DNSSEC ENABLE — {zone}',BOLD,not no_color))
    print(f'  plik strefy: {old_path}')
    print(f'  katalog kluczy: {key_dir}')
    if str(old_path).startswith('/etc/bind/'):
        target_path=target_dir/old_path.name
        print(c(f'  strefa zostanie przeniesiona do: {target_path}',YELLOW,not no_color))
    print('  operacje: backup, modyfikacja deklaracji zone, reconfig, podpisanie, generowanie DS')
    if not args.yes and not confirm('Kontynuować?',False):
        print('Anulowano.'); return 0
    if cmd_backup(cfg,zones,argparse.Namespace(no_color=no_color))!=0: return 1
    conf_path,conf_text,start=find_zone_config(zone,Path(t.get('bind_dir','/etc/bind')))
    conf_backup=conf_path.with_name(conf_path.name+f'.bak-dnssec-{dt.datetime.now().strftime("%Y%m%d-%H%M%S")}')
    zones_backup=args.zones_file.with_name(args.zones_file.name+f'.bak-dnssec-{dt.datetime.now().strftime("%Y%m%d-%H%M%S")}')
    shutil.copy2(conf_path,conf_backup); shutil.copy2(args.zones_file,zones_backup)
    copied=False
    try:
        key_dir.mkdir(parents=True,exist_ok=True)
        target_dir.mkdir(parents=True,exist_ok=True)
        if target_path!=old_path:
            shutil.copy2(old_path,target_path); copied=True
        for pth in (key_dir,target_dir,target_path):
            try: shutil.chown(pth,user='bind',group='bind')
            except LookupError: pass
        if target_path.is_file(): target_path.chmod(0o640)
        patch_zone_declaration(conf_path,conf_text,start,old_path,target_path,key_dir)
        update_ini_zone(args.zones_file,zone,new_path=target_path,dnssec=True)
        chk=run(['named-checkconf'])
        if chk.returncode!=0: raise RuntimeError('named-checkconf: '+(chk.stderr or chk.stdout).strip())
        zchk=run(['named-checkzone',zone,str(target_path)])
        if zchk.returncode!=0: raise RuntimeError('named-checkzone: '+(zchk.stderr or zchk.stdout).strip())
        rr=run(['rndc','reconfig'])
        if rr.returncode!=0: raise RuntimeError('rndc reconfig: '+(rr.stderr or rr.stdout).strip())
        server=t.get('local_server','127.0.0.1'); timeout=int(t.get('dig_timeout','3'))
        deadline=time.time()+args.wait
        print('Oczekiwanie na DNSKEY i RRSIG...',end='',flush=True)
        ready=False
        while time.time()<deadline:
            if local_dnskeys(server,zone,timeout) and has_rrsig(server,zone,'SOA',timeout): ready=True; break
            print('.',end='',flush=True); time.sleep(2)
        print()
        if not ready:
            raise RuntimeError(f'Strefa nie została podpisana w ciągu {args.wait} s. Sprawdź journalctl -u named.')
        ds=generate_ds(server,zone,timeout)
        print(c('OK   DNSKEY i RRSIG są dostępne.',GREEN,not no_color))
        print(c('Rekord DS do opublikowania w strefie nadrzędnej:',BOLD,not no_color))
        if ds:
            for line in ds: print('  '+line)
            ds_dir=Path(t.get('dnssec_ds_directory','/var/lib/elkman-dns-toolkit/ds')); ds_dir.mkdir(parents=True,exist_ok=True)
            ds_file=ds_dir/f'{zone}.ds'; ds_file.write_text('\n'.join(ds)+'\n'); print(f'Zapisano: {ds_file}')
        else: print(c('Nie udało się wygenerować DS.',RED,not no_color)); return 1
        print(c('UWAGA: dla subdomeny DS publikuje się w strefie nadrzędnej, niekoniecznie u rejestratora.',YELLOW,not no_color))
        print(f'Po publikacji uruchom: elkman-dns dnssec-check {zone}')
        if copied and old_path.exists():
            old_path.unlink()
            print(c(f'OK   Usunięto nieużywany stary plik: {old_path}',GREEN,not no_color))
        return 0
    except Exception:
        shutil.copy2(conf_backup,conf_path); shutil.copy2(zones_backup,args.zones_file)
        if copied: target_path.unlink(missing_ok=True)
        run(['rndc','reconfig'])
        raise


def tui_select(stdscr,title,items,status_lines=None):
    import curses
    curses.curs_set(0); stdscr.keypad(True); pos=0; top=0
    status_lines=status_lines or []
    while True:
        stdscr.erase(); h,w=stdscr.getmaxyx()
        stdscr.addstr(0,max(0,(w-len(title))//2),title[:w-1],curses.A_BOLD)
        y=2
        for line in status_lines:
            if y>=h-2: break
            stdscr.addstr(y,2,line[:max(1,w-4)]); y+=1
        if status_lines: y+=1
        visible=max(1,h-y-2)
        if pos<top: top=pos
        if pos>=top+visible: top=pos-visible+1
        for screen_i,i in enumerate(range(top,min(len(items),top+visible))):
            item=items[i]; yy=y+screen_i
            attr=curses.A_REVERSE if i==pos else curses.A_NORMAL
            stdscr.addstr(yy,2,item[:max(1,w-4)],attr)
        stdscr.addstr(h-1,1,'↑/↓ wybór   Enter zatwierdź   q/Esc powrót'[:max(1,w-2)])
        key=stdscr.getch()
        if key in (curses.KEY_UP,ord('k')): pos=(pos-1)%len(items)
        elif key in (curses.KEY_DOWN,ord('j')): pos=(pos+1)%len(items)
        elif key in (curses.KEY_NPAGE,): pos=min(len(items)-1,pos+visible)
        elif key in (curses.KEY_PPAGE,): pos=max(0,pos-visible)
        elif key in (10,13,curses.KEY_ENTER): return pos
        elif key in (ord('q'),27): return None


def human_age(path):
    if not path or not Path(path).exists(): return 'brak'
    sec=max(0,time.time()-Path(path).stat().st_mtime)
    if sec<60: return 'przed chwilą'
    if sec<3600: return f'{int(sec//60)} min temu'
    if sec<86400: return f'{int(sec//3600)} h temu'
    return f'{int(sec//86400)} dni temu'


def latest_backup(cfg):
    bdir=Path(cfg['toolkit'].get('backup_dir','/var/backups/elkman-dns'))
    files=sorted(bdir.glob('bind-*.tar.gz'),key=lambda p:p.stat().st_mtime,reverse=True) if bdir.exists() else []
    return files[0] if files else None


def zone_quick_status(cfg,zones,zone):
    t=cfg['toolkit']; item=zones[zone]; timeout=int(t.get('dig_timeout','3'))
    local=t.get('local_server','127.0.0.1'); dns2=t.get('dns2_server','5.172.189.198'); he=t.get('he_server','216.218.133.2')
    ls=dig_serial(local,zone,timeout)
    dns2_enabled=yes(item.get('dns2','yes'),True); he_enabled=yes(item.get('he','no'),False)
    ds=dig_serial(dns2,zone,timeout) if dns2_enabled else None
    hs=dig_serial(he,zone,timeout) if he_enabled else None
    dns2_ok=(not dns2_enabled) or (ls is not None and ds==ls)
    he_ok=(not he_enabled) or (ls is not None and hs==ls)
    dnssec_cfg=yes(item.get('dnssec','no'),False)
    dnskey=bool(local_dnskeys(local,zone,timeout)) if dnssec_cfg else False
    rrsig=has_rrsig(local,zone,'SOA',timeout) if dnssec_cfg else False
    notify_ok=yes(item.get('notify','yes'),True)
    health_ok=bool(ls) and dns2_ok and he_ok and ((dnskey and rrsig) if dnssec_cfg else True)
    return {'local_serial':ls,'dns2_serial':ds,'he_serial':hs,'dns2_ok':dns2_ok,'he_ok':he_ok,
            'dnssec':dnssec_cfg,'dnskey':dnskey,'rrsig':rrsig,'notify':notify_ok,'health':health_ok}


def domain_status_lines(cfg,zones,zone,quick=None):
    q=quick or zone_quick_status(cfg,zones,zone)
    tick=lambda x:'✔' if x else '✖'
    return [
        f'DNSSEC      {tick(q["dnssec"] and q["dnskey"] and q["rrsig"]) if q["dnssec"] else "—"}',
        f'DNS2        {tick(q["dns2_ok"])}',
        f'HE          {tick(q["he_ok"])}',
        f'Notify      {tick(q["notify"])}',
        f'Serial      {q["local_serial"] or "BRAK"}',
        f'Backup      {human_age(latest_backup(cfg))}',
        f'Health      {"PASS" if q["health"] else "FAIL"}',
    ]


def cmd_zone_serial(cfg,zones,args):
    require_root('serial')
    zone=args.zone; path=Path(zones[zone].get('file',''))
    if not path.exists(): raise RuntimeError(f'Brak pliku strefy: {path}')
    text=path.read_text()
    # Obsługuje typowy serial YYYYMMDDNN lub dowolną liczbę w rekordzie SOA.
    soa=re.search(r'(\bSOA\b[\s\S]*?\(\s*)(\d{8,10})(\s*;?\s*(?:serial|Serial)?)',text,re.I)
    if not soa:
        soa=re.search(r'(\bSOA\b[^\n]*\n(?:[^\n]*\n){0,4}?\s*)(\d{8,10})(\b)',text,re.I)
    if not soa: raise RuntimeError('Nie znaleziono numeru serial w rekordzie SOA.')
    old=soa.group(2); today=dt.datetime.now().strftime('%Y%m%d')
    if len(old)==10 and old.startswith(today): new=f'{today}{int(old[-2:])+1:02d}'
    elif len(old)==10: new=today+'01'
    else: new=str(int(old)+1)
    backup=path.with_name(path.name+f'.bak-serial-{dt.datetime.now().strftime("%Y%m%d-%H%M%S")}')
    shutil.copy2(path,backup)
    path.write_text(text[:soa.start(2)]+new+text[soa.end(2):])
    z=run(['named-checkzone',zone,str(path)])
    if z.returncode!=0:
        shutil.copy2(backup,path); raise RuntimeError('named-checkzone: '+(z.stderr or z.stdout).strip())
    print(c(f'OK   Serial {old} → {new}',GREEN,not args.no_color)); return 0


def cmd_zone_edit(cfg,zones,args):
    require_root('edit')
    zone=args.zone; path=Path(zones[zone].get('file',''))
    editor=os.environ.get('EDITOR','nano')
    backup=path.with_name(path.name+f'.bak-edit-{dt.datetime.now().strftime("%Y%m%d-%H%M%S")}')
    shutil.copy2(path,backup)
    rc=subprocess.call([editor,str(path)])
    if rc!=0: return rc
    z=run(['named-checkzone',zone,str(path)])
    if z.returncode!=0:
        print(c('FAIL named-checkzone — przywracam kopię.',RED,not args.no_color)); shutil.copy2(backup,path); return 1
    print(c(f'OK   Zapisano i zweryfikowano {path}',GREEN,not args.no_color)); return 0


def cmd_zone_report(cfg,zones,args):
    zone=args.zone; q=zone_quick_status(cfg,zones,zone); item=zones[zone]
    print(c(f'ZONE REPORT — {zone}',BOLD,not args.no_color)); print('='*(14+len(zone)))
    print(f'Plik .............. {item.get("file","")}')
    for line in domain_status_lines(cfg,zones,zone,q): print(line)
    print(f'DNS2 serial ....... {q["dns2_serial"] or "-"}')
    print(f'HE serial ......... {q["he_serial"] or "-"}')
    print('NS ................ '+', '.join(authoritative_servers(zone,int(cfg["toolkit"].get("dig_timeout","3")))))
    return 0 if q['health'] else 1


def cmd_backups(cfg,zones,args):
    bdir=Path(cfg['toolkit'].get('backup_dir','/var/backups/elkman-dns'))
    files=sorted(bdir.glob('bind-*.tar.gz'),key=lambda p:p.stat().st_mtime,reverse=True) if bdir.exists() else []
    if not files: print('Brak backupów.'); return 0
    for p in files[:30]: print(f'{dt.datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M:%S}  {p.stat().st_size//1024:>8} KiB  {p}')
    return 0


def domain_menu(cfg,zones,args,zone):
    import curses
    actions=['Health','DNSSEC','Reload','Notify','Backup','Edit','Serial +1','Secondary / Sync','Report','Powrót']
    while True:
        quick=zone_quick_status(cfg,zones,zone)
        idx=curses.wrapper(tui_select,zone,actions,domain_status_lines(cfg,zones,zone,quick))
        if idx is None or idx==len(actions)-1: return
        print()
        if idx==0: rc=cmd_health(cfg,zones,argparse.Namespace(no_color=args.no_color,zones=[zone]))
        elif idx==1: rc=cmd_dnssec_check(cfg,zones,argparse.Namespace(no_color=args.no_color,zones=[zone],explain=True)) if quick['dnssec'] else cmd_dnssec_enable(cfg,zones,argparse.Namespace(no_color=args.no_color,zone=zone,yes=False,wait=60,zones_file=args.zones_file))
        elif idx==2: rc=cmd_reload(cfg,zones,argparse.Namespace(zones=[zone],no_color=args.no_color,skip_check=False,no_notify=False))
        elif idx==3: rc=cmd_notify(cfg,zones,argparse.Namespace(zones=[zone],no_color=args.no_color))
        elif idx==4: rc=cmd_backup(cfg,zones,argparse.Namespace(no_color=args.no_color))
        elif idx==5: rc=cmd_zone_edit(cfg,zones,argparse.Namespace(zone=zone,no_color=args.no_color))
        elif idx==6: rc=cmd_zone_serial(cfg,zones,argparse.Namespace(zone=zone,no_color=args.no_color))
        elif idx==7: rc=cmd_sync(cfg,zones,argparse.Namespace(no_color=args.no_color))
        elif idx==8: rc=cmd_zone_report(cfg,zones,argparse.Namespace(zone=zone,no_color=args.no_color))
        else: rc=0
        input(f'\nKod zakończenia: {rc}. Naciśnij Enter, aby wrócić...')
        cfg,zones=load_config(args.config,args.zones_file)


def cmd_domains(cfg,zones,args):
    if not sys.stdin.isatty() or not sys.stdout.isatty(): raise RuntimeError('Domains wymaga TTY.')
    import curses
    while True:
        names=[z for z,_ in zone_items(zones)]
        labels=[]; states={}
        workers=min(8,max(1,len(names)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map={pool.submit(zone_quick_status,cfg,zones,z):z for z in names}
            for future in as_completed(future_map):
                z=future_map[future]
                try: states[z]=future.result()
                except Exception: states[z]=None
        for z in names:
            state=states.get(z)
            marker='🟢' if state and state['health'] else ('🔴' if state else '⚪')
            labels.append(f'{marker} {z}')
        labels.append('Powrót')
        idx=curses.wrapper(tui_select,'DOMAINS',labels)
        if idx is None or idx==len(names): return 0
        domain_menu(cfg,zones,args,names[idx])
        cfg,zones=load_config(args.config,args.zones_file)


def cmd_menu(cfg,zones,args):
    if not sys.stdin.isatty() or not sys.stdout.isatty(): raise RuntimeError('Menu wymaga interaktywnego terminala (TTY).')
    import curses
    actions=['Domains','Status wszystkich stref','Health wszystkich stref','Doctor','Backup teraz','Backup Manager','Wyjście']
    while True:
        choice=curses.wrapper(tui_select,'ELKMAN DNS TOOLKIT '+VERSION,actions)
        if choice is None or choice==len(actions)-1: return 0
        print()
        if choice==0: return_code=cmd_domains(cfg,zones,args)
        elif choice==1: return_code=cmd_sync(cfg,zones,argparse.Namespace(no_color=args.no_color))
        elif choice==2: return_code=cmd_health(cfg,zones,argparse.Namespace(no_color=args.no_color))
        elif choice==3: return_code=cmd_doctor(cfg,zones,argparse.Namespace(no_color=args.no_color,verbose=False))
        elif choice==4: return_code=cmd_backup(cfg,zones,argparse.Namespace(no_color=args.no_color))
        elif choice==5: return_code=cmd_backups(cfg,zones,argparse.Namespace(no_color=args.no_color))
        else: return_code=0
        if choice!=0: input(f'\nKod zakończenia: {return_code}. Naciśnij Enter, aby wrócić do menu...')
        cfg,zones=load_config(args.config,args.zones_file)

def cmd_update(cfg,zones,args):
    require_root('update')
    if cmd_backup(cfg,zones,args)!=0 or cmd_check(cfg,zones,argparse.Namespace(no_color=args.no_color))!=0: return 1
    if cmd_reload(cfg,zones,argparse.Namespace(zones=args.zones,no_color=args.no_color,skip_check=True,no_notify=False))!=0: return 1
    time.sleep(args.wait); return cmd_sync(cfg,zones,args)

def parser():
    p=argparse.ArgumentParser(prog='elkman-dns',description='elkman DNS Toolkit')
    p.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    p.add_argument('--zones-file',type=Path,default=DEFAULT_ZONES)
    p.add_argument('--no-color',action='store_true')
    p.add_argument('--version',action='version',version=f'%(prog)s {VERSION}')
    sp=p.add_subparsers(dest='command')
    for x in ('check','sync','health','backup','backups','menu','domains'): sp.add_parser(x)
    n=sp.add_parser('notify'); n.add_argument('zones',nargs='*')
    r=sp.add_parser('reload'); r.add_argument('zones',nargs='*'); r.add_argument('--skip-check',action='store_true'); r.add_argument('--no-notify',action='store_true')
    u=sp.add_parser('update'); u.add_argument('zones',nargs='*'); u.add_argument('--wait',type=int,default=15)
    s=sp.add_parser('dnssec-status'); s.add_argument('zones',nargs='*'); s.add_argument('-v','--verbose',action='store_true')
    q=sp.add_parser('dnssec-check'); q.add_argument('zones',nargs='*'); q.add_argument('--explain',action='store_true')
    rp=sp.add_parser('dnssec-report'); rp.add_argument('zones',nargs='*'); rp.add_argument('--json',action='store_true')
    en=sp.add_parser('dnssec-enable'); en.add_argument('zone'); en.add_argument('-y','--yes',action='store_true'); en.add_argument('--wait',type=int,default=60)
    ze=sp.add_parser('edit'); ze.add_argument('zone')
    zs=sp.add_parser('serial'); zs.add_argument('zone')
    zr=sp.add_parser('zone-report'); zr.add_argument('zone')
    d=sp.add_parser('doctor'); d.add_argument('-v','--verbose',action='store_true')
    return p

def main():
    args=parser().parse_args()
    if args.command is None:
        args.command='menu'
    try:
        cfg,zones=load_config(args.config,args.zones_file)
        commands={'check':cmd_check,'sync':cmd_sync,'health':cmd_health,'notify':cmd_notify,'reload':cmd_reload,'backup':cmd_backup,'update':cmd_update,'dnssec-status':cmd_dnssec_status,'dnssec-check':cmd_dnssec_check,'dnssec-report':cmd_dnssec_report,'dnssec-enable':cmd_dnssec_enable,'doctor':cmd_doctor,'edit':cmd_zone_edit,'serial':cmd_zone_serial,'zone-report':cmd_zone_report,'backups':cmd_backups,'domains':cmd_domains,'menu':cmd_menu}
        return commands[args.command](cfg,zones,args)
    except KeyboardInterrupt:
        print(c('\nPrzerwano przez użytkownika.',YELLOW,not getattr(args,'no_color',False)),file=sys.stderr); return 130
    except Exception as exc:
        print(c(f'BŁĄD: {exc}',RED,not getattr(args,'no_color',False)),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
