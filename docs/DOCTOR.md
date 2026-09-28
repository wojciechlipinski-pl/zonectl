# ZoneCTL Doctor and safe GitHub reports

`zctl doctor` performs bounded, read-only checks of the ZoneCTL host. It does
not reload BIND, write configuration, modify DNSSEC state or contact GitHub.

## Diagnostic contract

The JSON output uses schema `zonectl.doctor/v1`. It contains only:

- the overall `PASS`, `WARN` or `BLOCKED` result;
- ZoneCTL, BIND and package versions;
- stable check codes, classifications, generic summaries and suggested next
  steps.

It deliberately excludes zone names, IP addresses, host and user names,
environment paths, contact details, command output, DNSKEY material, DS
digests, tokens and credentials.

```bash
zctl doctor
zctl doctor --json
```

## Preparing a GitHub report on a headless server

The following command writes a private mode-`0600` Markdown report and prints
a pre-filled GitHub Issue URL. Nothing is submitted automatically:

```bash
zctl doctor --prepare-issue
```

Copy the URL to a browser on another computer, review the form and submit it
while logged in to GitHub. When the complete body would exceed the conservative
URL limit, ZoneCTL opens the dedicated template without embedding the body and
instructs the operator to paste the private local report instead.

## Optional authenticated submission

ZoneCTL never stores a GitHub password or token. When an administrator has
installed GitHub CLI and authenticated it separately, an Issue can be created
after a public preview and explicit confirmation:

```bash
gh auth login
zctl doctor --prepare-issue --submit-github --confirm-public 'WYŚLIJ'
```

Before calling `gh issue create`, ZoneCTL:

1. builds the report from an allowlist;
2. scans it again for addresses, paths, email addresses and key-like values;
3. displays the complete public body;
4. requires the exact confirmation `WYŚLIJ`.

If `gh` is missing, authentication fails or GitHub rejects the request, no
Issue is created and the local report remains available. Full system logs and
attachments are never uploaded automatically.

## TUI

Press `F5` on the main screen. After the read-only check, choose:

- `LINK` to display a browser-copyable URL;
- `ZAPISZ` to keep only the local report;
- `WYŚLIJ` to use an existing authenticated `gh` session.

The public-send path shows the complete body and requires `WYŚLIJ` a second
time.

---

# ZoneCTL Doctor i bezpieczne zgłoszenia GitHub

`zctl doctor` wykonuje ograniczone kontrole hosta wyłącznie do odczytu. Nie
przeładowuje BIND, nie zapisuje konfiguracji, nie zmienia stanu DNSSEC i bez
wyraźnej decyzji operatora nie kontaktuje się z GitHubem.

Raport publiczny zawiera jedynie klasyfikację, wersje, stabilne kody kontroli,
ogólne opisy i zalecane następne kroki. Nie zbiera nazw stref, adresów, nazw
hostów i użytkowników, ścieżek środowiskowych, danych kontaktowych, surowego
wyjścia poleceń, kluczy, skrótów DS ani poświadczeń.

Na serwerze bez interfejsu graficznego użyj:

```bash
zctl doctor --prepare-issue
```

Program zapisze prywatny raport oraz wyświetli link do skopiowania na komputer
z przeglądarką. Automatyczna wysyłka jest opcjonalna i działa wyłącznie przez
wcześniej uwierzytelnionego klienta `gh`, po podglądzie i jawnym potwierdzeniu
`WYŚLIJ`.
