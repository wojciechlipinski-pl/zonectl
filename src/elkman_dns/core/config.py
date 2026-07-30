from __future__ import annotations

import configparser
from pathlib import Path

from .discovery import (
    BindConfigDiscovery,
    BindDiscoveryError,
    DEFAULT_NAMED_CONF,
    ZoneConfig,
)
from .models import Zone


DEFAULT_CONFIG = Path("/etc/elkman-dns-toolkit/toolkit.conf")
DEFAULT_ZONES = Path("/etc/elkman-dns-toolkit/zones.conf")
DEFAULT_GROUPS = Path("/etc/elkman-dns-toolkit/groups.yaml")


def _yes(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "yes",
        "true",
        "on",
        "tak",
    }


def _unquote(value: str) -> str:
    value = value.strip()

    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {'"', "'"}
    ):
        return value[1:-1]

    return value


def load_groups_yaml(
    path: Path,
) -> tuple[list[str], dict[str, str]]:
    """Odczytaj uproszczony format groups.yaml bez PyYAML."""

    if not path.exists():
        return [], {}

    order: list[str] = []
    mapping: dict[str, str] = {}
    current: str | None = None
    seen_root = False

    for number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "groups:":
            seen_root = True
            current = None
            continue

        if not seen_root:
            raise RuntimeError(
                f"{path}:{number}: oczekiwano 'groups:'"
            )

        indent = len(line) - len(line.lstrip(" "))

        if indent == 2 and stripped.endswith(":"):
            current = _unquote(stripped[:-1].strip())

            if not current:
                raise RuntimeError(
                    f"{path}:{number}: pusta nazwa grupy"
                )

            if current not in order:
                order.append(current)

            continue

        if (
            indent >= 4
            and stripped.startswith("- ")
            and current
        ):
            zone = (
                _unquote(stripped[2:].strip())
                .rstrip(".")
                .casefold()
            )

            if not zone:
                raise RuntimeError(
                    f"{path}:{number}: pusta domena"
                )

            mapping[zone] = current
            continue

        raise RuntimeError(
            f"{path}:{number}: nieobsługiwana składnia"
        )

    return order, mapping


class ToolkitConfig:
    """
    Konfiguracja ZoneCTL.

    Konfiguracja BIND jest źródłem prawdy dla:

    - nazw stref,
    - typów stref,
    - aktywnych plików źródłowych.

    zones.conf może nadpisywać wyłącznie ustawienia Toolkitu,
    np. grupę, obsługę serwerów wtórnych i widoczność strefy.
    """

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

        self.discovered_zone_configs: dict[str, ZoneConfig] = {}
        self.discovery_config_files: tuple[Path, ...] = ()

    def load(self) -> "ToolkitConfig":
        if not self.config_path.exists():
            raise RuntimeError(
                f"Brak pliku konfiguracji: {self.config_path}"
            )

        self.general.read(
            self.config_path,
            encoding="utf-8",
        )

        if "toolkit" not in self.general:
            raise RuntimeError(
                f"Brak sekcji [toolkit] w {self.config_path}"
            )

        # zones.conf staje się opcjonalny.
        if self.zones_path.exists():
            self.zone_config.read(
                self.zones_path,
                encoding="utf-8",
            )

        self.group_order, self.group_mapping = load_groups_yaml(
            self.groups_path
        )

        if self.auto_discover_zones:
            self._discover_bind_zones()

        return self

    @property
    def toolkit(self) -> configparser.SectionProxy:
        return self.general["toolkit"]

    @property
    def auto_discover_zones(self) -> bool:
        return _yes(
            self.toolkit.get("auto_discover_zones"),
            True,
        )

    @property
    def bind_config_path(self) -> Path:
        raw = self.toolkit.get(
            "bind_config",
            str(DEFAULT_NAMED_CONF),
        ).strip()

        return Path(raw).expanduser()

    @staticmethod
    def _normalise_zone_name(name: str) -> str:
        return name.rstrip(".").casefold()

    def _discover_bind_zones(self) -> None:
        try:
            result = BindConfigDiscovery(
                self.bind_config_path
            ).discover()
        except BindDiscoveryError as exc:
            raise RuntimeError(
                f"Autodetekcja konfiguracji BIND nie powiodła się: "
                f"{exc}"
            ) from exc

        self.discovery_config_files = result.config_files
        self.discovered_zone_configs = {
            self._normalise_zone_name(zone.name): zone
            for zone in result.zones
        }

    def discovered_zone(
        self,
        name: str,
    ) -> ZoneConfig | None:
        return self.discovered_zone_configs.get(
            self._normalise_zone_name(name)
        )

    def _zone_override(
        self,
        name: str,
    ) -> configparser.SectionProxy | None:
        wanted = self._normalise_zone_name(name)

        for section_name in self.zone_config.sections():
            if self._normalise_zone_name(section_name) == wanted:
                return self.zone_config[section_name]

        return None

    def _group_for(
        self,
        name: str,
        override: configparser.SectionProxy | None,
    ) -> str:
        if override is not None:
            explicit = override.get("group", "").strip()

            if explicit:
                return explicit

        return self.group_mapping.get(
            self._normalise_zone_name(name),
            "Pozostałe",
        )

    def _zone_from_discovery(
        self,
        discovered: ZoneConfig,
    ) -> Zone | None:
        override = self._zone_override(discovered.name)

        if override is not None:
            enabled = _yes(
                override.get("enabled"),
                True,
            )
        else:
            enabled = True

        if not enabled:
            return None

        # Edytor pokazuje wyłącznie strefy primary/master.
        if not discovered.is_primary:
            return None

        # Nie pokazujemy stref bez parametru file.
        if discovered.source_file is None:
            return None

        # Nigdy nie traktujemy pliku .signed jako źródła.
        if discovered.is_managed_signed_file:
            return None

        return Zone(
            name=discovered.name,
            file=discovered.source_file,
            enabled=True,
            dns2=_yes(
                override.get("dns2") if override else None,
                True,
            ),
            he=_yes(
                override.get("he") if override else None,
                False,
            ),
            notify=_yes(
                override.get("notify") if override else None,
                True,
            ),
            reload=_yes(
                override.get("reload") if override else None,
                True,
            ),
            group=self._group_for(
                discovered.name,
                override,
            ),
        )

    def _zones_from_discovery(self) -> list[Zone]:
        result: list[Zone] = []

        for discovered in sorted(
            self.discovered_zone_configs.values(),
            key=lambda item: item.name.casefold(),
        ):
            zone = self._zone_from_discovery(discovered)

            if zone is not None:
                result.append(zone)

        return result

    def _zones_from_legacy_config(self) -> list[Zone]:
        """
        Tryb zgodności ze starym zones.conf.

        Używany wyłącznie, gdy auto_discover_zones = no.
        """
        if not self.zones_path.exists():
            raise RuntimeError(
                "Autodetekcja stref jest wyłączona, ale nie istnieje "
                f"plik {self.zones_path}"
            )

        result: list[Zone] = []

        for name in sorted(
            self.zone_config.sections(),
            key=str.casefold,
        ):
            item = self.zone_config[name]
            enabled = _yes(
                item.get("enabled"),
                True,
            )

            if not enabled:
                continue

            raw_file = item.get("file", "").strip()
            explicit_group = item.get("group", "").strip()

            group = (
                explicit_group
                or self.group_mapping.get(
                    self._normalise_zone_name(name),
                    "Pozostałe",
                )
            )

            result.append(
                Zone(
                    name=name,
                    file=Path(raw_file) if raw_file else None,
                    enabled=enabled,
                    dns2=_yes(
                        item.get("dns2"),
                        True,
                    ),
                    he=_yes(
                        item.get("he"),
                        False,
                    ),
                    notify=_yes(
                        item.get("notify"),
                        True,
                    ),
                    reload=_yes(
                        item.get("reload"),
                        True,
                    ),
                    group=group,
                )
            )

        return result

    def zones(self) -> list[Zone]:
        if self.auto_discover_zones:
            return self._zones_from_discovery()

        return self._zones_from_legacy_config()
