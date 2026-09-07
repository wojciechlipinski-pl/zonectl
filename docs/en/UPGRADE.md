# Upgrading from a GitHub release

ZoneCTL provides `scripts/install-latest-release.sh` for guarded upgrades on a
Debian production host. Run the read-only check first:

```bash
sudo ./scripts/install-latest-release.sh --check
```

Install the newest stable (non-draft, non-prerelease) GitHub release:

```bash
sudo ./scripts/install-latest-release.sh
```

To select a specific stable release:

```bash
sudo ./scripts/install-latest-release.sh --version v4.12.0
```

The script downloads the Debian package and `SHA256SUMS` from the public
`wojciechlipinski-pl/zonectl` release, verifies the checksum and Debian package
metadata, and refuses an accidental downgrade. Immediately before and after
installation it validates the BIND configuration and requires `bind9` to be
active. It does not modify BIND configuration or zone files directly.

Requirements are `curl`, `python3`, `sha256sum`, `dpkg-deb`, `dpkg-query`,
`apt-get`, `flock`, `named-checkconf`, and `systemctl`. Run the script locally
on the target host as root or through `sudo`; do not pipe a remote script
directly into a root shell.

The checksum published beside an asset protects against transfer corruption.
It does not replace review of the GitHub repository, release workflow, and tag
when the GitHub account itself is outside the threat model.

## Failed final validation

If package installation started but a final check failed, inspect the state:

```bash
dpkg-query -W zonectl
zctl --version
named-checkconf
systemctl status bind9 --no-pager
```

The script deliberately does not downgrade automatically. Reinstall the
previous version only from a separately verified package or trusted APT
source, after diagnosing the failure. The ZoneCTL package does not own
`/etc/bind`; installing it should not modify BIND configuration or zone files.
