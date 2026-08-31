from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Iterable

from .zone_model import ChangeKind, ZoneRecordView


class RecordFilterError(ValueError):
    """Nieprawidłowe wyrażenie filtrowania rekordów."""


_EXPRESSION = re.compile(
    r"^(name|owner|type|ttl|value|data|status|change)"
    r"(!=|>=|<=|=|:|~|>|<)(.+)$",
    re.IGNORECASE,
)

_STATUS_NAMES = {
    "add": "added",
    "added": "added",
    "dodano": "added",
    "+": "added",
    "modify": "modified",
    "modified": "modified",
    "zmieniono": "modified",
    "~": "modified",
    "delete": "deleted",
    "deleted": "deleted",
    "usunięto": "deleted",
    "usunieto": "deleted",
    "-": "deleted",
    "unchanged": "unchanged",
    "bez-zmian": "unchanged",
    "bez_zmian": "unchanged",
    "normal": "unchanged",
}


@dataclass(frozen=True, slots=True)
class FilterTerm:
    field: str | None
    operator: str
    value: str
    negated: bool = False
    pattern: re.Pattern[str] | None = None


def _status(view: ZoneRecordView) -> str:
    return {
        ChangeKind.ADD: "added",
        ChangeKind.MODIFY: "modified",
        ChangeKind.DELETE: "deleted",
        None: "unchanged",
    }[view.change_kind]


class RecordFilter:
    """
    Skompilowany filtr rekordów.

    Oddzielone spacjami warunki są łączone operatorem AND. Zwykły tekst
    zachowuje dotychczasowe wyszukiwanie we wszystkich widocznych polach.
    """

    def __init__(self, query: str):
        self.query = query.strip()
        self.terms = self._parse(self.query)

    @staticmethod
    def _parse(query: str) -> tuple[FilterTerm, ...]:
        if not query:
            return ()

        try:
            tokens = shlex.split(query)
        except ValueError as exc:
            raise RecordFilterError(f"Nieprawidłowe cudzysłowy: {exc}") from exc

        terms: list[FilterTerm] = []

        for original in tokens:
            negated = original.startswith("-") and len(original) > 1
            token = original[1:] if negated else original
            match = _EXPRESSION.fullmatch(token)

            if match is None:
                terms.append(
                    FilterTerm(
                        field=None,
                        operator=":",
                        value=token.casefold(),
                        negated=negated,
                    )
                )
                continue

            field, operator, value = match.groups()
            field = {
                "owner": "name",
                "data": "value",
                "change": "status",
            }.get(field.casefold(), field.casefold())
            value = value.strip()

            if not value:
                raise RecordFilterError(f"Brak wartości filtra: {original}")

            pattern = None
            if operator == "~":
                try:
                    pattern = re.compile(value, re.IGNORECASE)
                except re.error as exc:
                    raise RecordFilterError(
                        f"Nieprawidłowe wyrażenie regularne {value!r}: {exc}"
                    ) from exc

            if field == "ttl" and operator in {
                ":",
                "=",
                "!=",
                ">",
                "<",
                ">=",
                "<=",
            }:
                if value != "-":
                    try:
                        int(value)
                    except ValueError as exc:
                        raise RecordFilterError(
                            f"TTL musi być liczbą lub '-': {value}"
                        ) from exc
            elif field == "ttl":
                raise RecordFilterError(
                    f"Operator {operator!r} nie jest obsługiwany dla TTL"
                )
            elif operator in {">", "<", ">=", "<="}:
                raise RecordFilterError(
                    f"Operator {operator!r} jest dostępny tylko dla TTL"
                )

            if field == "status":
                normalized = _STATUS_NAMES.get(value.casefold())
                if normalized is None:
                    raise RecordFilterError(
                        "Status musi mieć wartość: added, modified, "
                        "deleted lub unchanged"
                    )
                value = normalized

            terms.append(
                FilterTerm(
                    field=field,
                    operator=operator,
                    value=value,
                    negated=negated,
                    pattern=pattern,
                )
            )

        return tuple(terms)

    @staticmethod
    def _text_value(
        term: FilterTerm,
        view: ZoneRecordView,
        zone_name: str,
    ) -> str:
        record = view.record
        if term.field == "name":
            return record.relative_owner(zone_name)
        if term.field == "type":
            return record.rtype
        if term.field == "value":
            return record.rdata
        if term.field == "status":
            return _status(view)
        raise RecordFilterError(f"Nieobsługiwane pole filtra: {term.field}")

    @staticmethod
    def _match_ttl(term: FilterTerm, view: ZoneRecordView) -> bool:
        ttl = view.record.ttl
        wanted = None if term.value == "-" else int(term.value)

        if term.operator in {":", "="}:
            return ttl == wanted
        if term.operator == "!=":
            return ttl != wanted
        if ttl is None or wanted is None:
            return False
        if term.operator == ">":
            return ttl > wanted
        if term.operator == "<":
            return ttl < wanted
        if term.operator == ">=":
            return ttl >= wanted
        if term.operator == "<=":
            return ttl <= wanted
        raise RecordFilterError(
            f"Operator {term.operator!r} nie jest obsługiwany dla TTL"
        )

    @classmethod
    def _match_term(
        cls,
        term: FilterTerm,
        view: ZoneRecordView,
        zone_name: str,
    ) -> bool:
        if term.field is None:
            record = view.record
            haystack = " ".join(
                (
                    view.marker,
                    record.relative_owner(zone_name),
                    record.rtype,
                    "-" if record.ttl is None else str(record.ttl),
                    record.rdata,
                    _status(view),
                )
            ).casefold()
            matched = term.value in haystack
        elif term.field == "ttl":
            matched = cls._match_ttl(term, view)
        else:
            actual = cls._text_value(term, view, zone_name)
            expected = term.value

            if term.operator == ":":
                if term.field in {"type", "status"}:
                    matched = actual.casefold() == expected.casefold()
                else:
                    matched = expected.casefold() in actual.casefold()
            elif term.operator == "=":
                matched = actual.casefold() == expected.casefold()
            elif term.operator == "!=":
                matched = actual.casefold() != expected.casefold()
            elif term.operator == "~":
                assert term.pattern is not None
                matched = term.pattern.search(actual) is not None
            else:
                raise RecordFilterError(
                    f"Operator {term.operator!r} nie jest obsługiwany "
                    f"dla pola {term.field}"
                )

        return not matched if term.negated else matched

    def matches(
        self,
        view: ZoneRecordView,
        zone_name: str,
    ) -> bool:
        return all(self._match_term(term, view, zone_name) for term in self.terms)

    def apply(
        self,
        records: Iterable[ZoneRecordView],
        zone_name: str,
    ) -> list[ZoneRecordView]:
        return [view for view in records if self.matches(view, zone_name)]
