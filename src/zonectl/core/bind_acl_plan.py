"""Read-only, validated cleanup plan for one BIND ACL."""

from __future__ import annotations

import difflib
import ipaddress
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .bind_access_inventory import BindAccessInventoryReader
from .runner import run
from .discovery import BindConfigDiscovery


class BindAclPlanError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BindAclPlan:
    name: str
    source: Path
    original_text: str
    candidate_text: str
    diff: str
    replacements: tuple[str, ...]
    removed_duplicates: tuple[str, ...]
    validation_ok: bool
    validation_message: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["source"] = str(self.source)
        data["replacements"] = list(self.replacements)
        data["removed_duplicates"] = list(self.removed_duplicates)
        return data


class BindAclPlanner:
    _acl = re.compile(
        r'\bacl\s+(?:["\'](?P<quoted>[^"\']+)["\']|(?P<plain>[A-Za-z0-9_.-]+))\s*\{',
        re.IGNORECASE,
    )

    def __init__(self, root_config: Path = Path("/etc/bind/named.conf")) -> None:
        self.root_config = root_config.expanduser().resolve()

    def plan(
        self,
        name: str,
        *,
        replacements: dict[str, str] | None = None,
        remove_duplicates: bool = True,
    ) -> BindAclPlan:
        inventory = BindAccessInventoryReader(self.root_config).collect()
        matches = [
            item for item in inventory.definitions
            if item.kind == "acl" and item.name.casefold() == name.casefold()
        ]
        if len(matches) != 1:
            raise BindAclPlanError(
                f"ACL {name} ma {len(matches)} aktywnych definicji; wymagano jednej"
            )
        definition = matches[0]
        original = definition.source.read_text(encoding="utf-8", errors="replace")
        masked = BindAccessInventoryReader._mask_comments(original)
        match = next(
            (
                found for found in self._acl.finditer(masked)
                if (found.group("quoted") or found.group("plain")).casefold()
                == name.casefold()
            ),
            None,
        )
        if match is None:
            raise BindAclPlanError(f"Nie można wydzielić bloku ACL {name}")
        opening = masked.find("{", match.start(), match.end())
        closing = BindConfigDiscovery._find_block_end(masked, opening, definition.source)
        body = original[opening + 1 : closing]
        candidate_body, changed, removed = self._rewrite_body(
            body, replacements or {}, remove_duplicates
        )
        candidate = original[: opening + 1] + candidate_body + original[closing:]
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                candidate.splitlines(keepends=True),
                fromfile=str(definition.source),
                tofile=f"{definition.source} (kandydat ACL)",
            )
        )
        validation_ok, validation_message = self._validate_candidate(
            definition.source, candidate
        )
        return BindAclPlan(
            name=name,
            source=definition.source,
            original_text=original,
            candidate_text=candidate,
            diff=diff,
            replacements=tuple(changed),
            removed_duplicates=tuple(removed),
            validation_ok=validation_ok,
            validation_message=validation_message,
        )

    @staticmethod
    def _rewrite_body(
        body: str, replacements: dict[str, str], remove_duplicates: bool
    ) -> tuple[str, list[str], list[str]]:
        seen: set[str] = set()
        changed: list[str] = []
        removed: list[str] = []
        entry = re.compile(
            r"(?m)^(?P<indent>[ \t]*)(?P<value>!?[A-Za-z0-9:./_-]+)"
            r"(?P<tail>[ \t]*;[^\r\n]*)(?P<newline>\r?\n|$)"
        )

        def rewrite(match: re.Match[str]) -> str:
            raw = match.group("value")
            replacement = replacements.get(raw, raw)
            if replacement != raw:
                changed.append(f"{raw} -> {replacement}")
            key = BindAclPlanner._normalized(replacement)
            if remove_duplicates and key in seen:
                removed.append(replacement)
                return ""
            seen.add(key)
            return (
                match.group("indent")
                + replacement
                + match.group("tail")
                + match.group("newline")
            )

        return entry.sub(rewrite, body), changed, removed

    @staticmethod
    def _normalized(value: str) -> str:
        negated = value.startswith("!")
        item = value.lstrip("!").strip()
        try:
            normalized = str(ipaddress.ip_network(item, strict=False))
        except ValueError:
            normalized = item.casefold()
        return ("!" if negated else "") + normalized

    def _validate_candidate(self, source: Path, candidate: str) -> tuple[bool, str]:
        temporary_root = Path(tempfile.mkdtemp(prefix="zonectl-acl-plan-"))
        try:
            config_root = self.root_config.parent
            relative_source = source.relative_to(config_root)
            paths = BindConfigDiscovery(self.root_config).discover().config_files
            for path in paths:
                relative = path.relative_to(config_root)
                target = temporary_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                copied = path.read_text(encoding="utf-8", errors="replace").replace(
                    str(config_root), str(temporary_root)
                )
                target.write_text(copied, encoding="utf-8")
            candidate_copy = candidate.replace(str(config_root), str(temporary_root))
            (temporary_root / relative_source).write_text(
                candidate_copy, encoding="utf-8"
            )
            root_copy = temporary_root / self.root_config.relative_to(config_root)
            outcome = run(["named-checkconf", str(root_copy)], 30)
            detail = (outcome.stdout or outcome.stderr).strip() or f"kod {outcome.returncode}"
            return outcome.returncode == 0, detail
        except (OSError, ValueError) as exc:
            return False, str(exc)
        finally:
            shutil.rmtree(temporary_root, ignore_errors=True)
