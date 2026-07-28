from __future__ import annotations

import configparser
from pathlib import Path

from .models import Zone
from .bind_config import BindConfigDiscovery, BindConfigError
DEFAULT_CONFIG = Path("/etc/elkman-dns-toolkit/toolkit.conf")
DEFAULT_ZONES = Path("/etc/elkman-dns-toolkit/zones.conf")
DEFAULT_GROUPS = Path("/etc/elkman-dns-toolkit/groups.yaml")


def _yes(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "yes", "true", "on", "tak"}


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def load_groups_yaml(path: Path) -> tuple[list[str], dict[str, str]]:
    """Read the intentionally small groups.yaml format without PyYAML.

    Supported form:
        groups:
          Group name:
            - zone.example

    Blank lines and # comments are ignored. A malformed file raises RuntimeError
    instead of silently assigning domains to wrong groups.
    """
    if not path.exists():
        return [], {}
    order: list[str] = []
    mapping: dict[str, str] = {}
    current: str | None = None
    seen_root = False
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "groups:":
            seen_root = True
            current = None
            continue
        if not seen_root:
            raise RuntimeError(f"{path}:{number}: oczekiwano 'groups:'")
        indent = len(line) - len(line.lstrip(" "))
        if indent == 2 and stripped.endswith(":"):
            current = _unquote(stripped[:-1].strip())
            if not current:
                raise RuntimeError(f"{path}:{number}: pusta nazwa grupy")
            if current not in order:
                order.append(current)
            continue
        if indent >= 4 and stripped.startswith("- ") and current:
            zone = _unquote(stripped[2:].strip()).rstrip(".").casefold()
            if not zone:
                raise RuntimeError(f"{path}:{number}: pusta domena")
            mapping[zone] = current
            continue
        raise RuntimeError(f"{path}:{number}: nieobsługiwana składnia")
    return order, mapping


class ToolkitConfig:
    def __init__(
        self,
        config_path: Path = DEFAULT_CONFIG,
        zones_path: Path = DEFAULT_ZONES,
        groups_path: Path = DEFAULT_GROUPS,
    ):
        self.config_path = config_path
        self.zones_path = zones_path
        self.groups_path = groups_path
        self.general = configparser.ConfigParser()
        self.zone_config = configparser.ConfigParser()
        self.group_order: list[str] = []
        self.group_mapping: dict[str, str] = {}

    def load(self) -> "ToolkitConfig":
        """
        Wczytuje konfigurację toolkitu.

        Konfiguracja BIND jest podstawowym źródłem stref.
        zones.conf i groups.yaml są opcjonalnymi źródłami
        zgodności wstecznej.
        """
        if not self.config_path.exists():
            raise RuntimeError(
                f"Brak pliku konfiguracji: {self.config_path}"
            )

        self.general.read(self.config_path)

        if "toolkit" not in self.general:
            raise RuntimeError(
                f"Brak sekcji [toolkit] w {self.config_path}"
            )

        # zones.conf jest od teraz tylko awaryjnym źródłem stref.
        if self.zones_path.exists():
            self.zone_config.read(self.zones_path)

        # groups.yaml jest opcjonalny. Parser BIND potrafi
        # sam przypisać podstawowe grupy: Publiczne, RPZ
        # oraz Strefy odwrotne.
        if self.groups_path.exists():
            self.group_order, self.group_mapping = (
                load_groups_yaml(self.groups_path)
            )
        else:
            self.group_order = []
            self.group_mapping = {}

        return self

    @property
    def toolkit(self) -> configparser.SectionProxy:
        return self.general["toolkit"]

    def zones(self) -> list[Zone]:
        """
        Zwraca strefy wykryte w rzeczywistej konfiguracji BIND.

        zones.conf jest używany wyłącznie wtedy, gdy konfiguracji
        BIND nie da się odczytać lub przeanalizować.
        """
        bind_root = Path(
            self.toolkit.get(
                "bind_config",
                "/etc/bind/named.conf.local",
            )
        )

        bind_error: BindConfigError | None = None

        try:
            zones = BindConfigDiscovery(bind_root).zones()

            if zones:
                return self._apply_group_overrides(zones)

            bind_error = BindConfigError(
                f"Nie znaleziono stref w {bind_root}"
            )
        except BindConfigError as exc:
            bind_error = exc

        fallback = self._zones_from_legacy_config()

        if fallback:
            return fallback

        raise RuntimeError(
            "Nie udało się odczytać żadnych stref. "
            f"Błąd konfiguracji BIND: {bind_error}. "
            f"Brak poprawnego fallbacku: {self.zones_path}"
        )

    def _apply_group_overrides(
        self,
        zones: list[Zone],
    ) -> list[Zone]:
        """Nakłada ręczne grupy z groups.yaml, jeżeli istnieją."""
        if not self.group_mapping:
            return zones

        result: list[Zone] = []

        for zone in zones:
            key = zone.name.rstrip(".").casefold()
            override = self.group_mapping.get(key)

            if not override:
                result.append(zone)
                continue

            result.append(
                Zone(
                    name=zone.name,
                    file=zone.file,
                    enabled=zone.enabled,
                    dns2=zone.dns2,
                    he=zone.he,
                    notify=zone.notify,
                    reload=zone.reload,
                    group=override,
                )
            )

        return result

    def _zones_from_legacy_config(self) -> list[Zone]:
        """Wczytuje opcjonalny fallback ze starego zones.conf."""
        result: list[Zone] = []

        for name in sorted(
            self.zone_config.sections(),
            key=str.casefold,
        ):
            item = self.zone_config[name]
            enabled = _yes(item.get("enabled"), True)

            if not enabled:
                continue

            raw_file = item.get("file", "").strip()
            explicit_group = item.get("group", "").strip()

            group = (
                explicit_group
                or self.group_mapping.get(
                    name.rstrip(".").casefold(),
                    "Pozostałe",
                )
            )

            result.append(
                Zone(
                    name=name,
                    file=Path(raw_file) if raw_file else None,
                    enabled=enabled,
                    dns2=_yes(item.get("dns2"), True),
                    he=_yes(item.get("he"), False),
                    notify=_yes(item.get("notify"), True),
                    reload=_yes(item.get("reload"), True),
                    group=group,
                )
            )

        return result
