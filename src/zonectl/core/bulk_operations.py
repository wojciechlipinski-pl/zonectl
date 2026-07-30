from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, replace
from enum import Enum

from .record_filter import RecordFilter, RecordFilterError
from .record_validation import validate_record
from .zone_model import ZoneModel, ZoneRecordView
from .zone_parser import DNSRecord


class BulkOperationError(ValueError):
    """Nieprawidłowa lub niemożliwa operacja masowa."""


class BulkAction(str, Enum):
    SET = "SET"
    DELETE = "DELETE"


@dataclass(frozen=True, slots=True)
class BulkMatch:
    identifier: int
    before: DNSRecord
    after: DNSRecord | None


@dataclass(frozen=True, slots=True)
class BulkOperation:
    query: str
    action: BulkAction
    field: str | None = None
    value: str | None = None

    _COMMAND = re.compile(
        r"^\s*SELECT\s+(.+?)\s+(SET\s+.+|DELETE)\s*$",
        re.IGNORECASE,
    )

    @classmethod
    def parse(cls, command: str) -> "BulkOperation":
        match = cls._COMMAND.fullmatch(command)
        if match is None:
            raise BulkOperationError(
                "Oczekiwany format: SELECT <filtr> "
                "SET ttl=<wartość>, SET value=<wartość> lub DELETE"
            )

        query, action_text = match.groups()
        try:
            RecordFilter(query)
        except RecordFilterError as exc:
            raise BulkOperationError(str(exc)) from exc

        if action_text.strip().casefold() == "delete":
            return cls(query=query, action=BulkAction.DELETE)

        try:
            tokens = shlex.split(action_text)
        except ValueError as exc:
            raise BulkOperationError(
                f"Nieprawidłowe cudzysłowy: {exc}"
            ) from exc

        if len(tokens) != 2 or tokens[0].casefold() != "set":
            raise BulkOperationError(
                "SET wymaga jednego przypisania, np. SET ttl=7200"
            )

        assignment = tokens[1]
        if "=" not in assignment:
            raise BulkOperationError(
                "Brak znaku '=' w przypisaniu SET"
            )

        field, value = assignment.split("=", 1)
        field = {
            "rdata": "value",
            "data": "value",
        }.get(field.casefold(), field.casefold())

        if field not in {"ttl", "value"}:
            raise BulkOperationError(
                "SET obsługuje obecnie pola ttl i value"
            )
        if value == "":
            raise BulkOperationError(
                f"Wartość pola {field} nie może być pusta"
            )
        if field == "ttl" and value != "-":
            try:
                ttl = int(value)
            except ValueError as exc:
                raise BulkOperationError(
                    "TTL musi być liczbą lub '-'"
                ) from exc
            if not 0 <= ttl <= 2147483647:
                raise BulkOperationError(
                    "TTL musi mieć zakres 0–2147483647"
                )

        return cls(
            query=query,
            action=BulkAction.SET,
            field=field,
            value=value,
        )

    def selected(
        self,
        model: ZoneModel,
    ) -> list[ZoneRecordView]:
        visible = [
            view
            for view in model.record_views
            if not view.deleted
        ]
        return RecordFilter(self.query).apply(
            visible,
            model.zone_name,
        )

    def _replacement(self, record: DNSRecord) -> DNSRecord:
        if self.action is not BulkAction.SET:
            raise BulkOperationError(
                "Operacja DELETE nie tworzy rekordu zastępczego"
            )
        if self.field == "ttl":
            ttl = None if self.value == "-" else int(self.value or "")
            candidate = replace(record, ttl=ttl)
        elif self.field == "value":
            candidate = replace(record, rdata=self.value or "")
        else:
            raise BulkOperationError("Brak obsługiwanego pola SET")

        issues = validate_record(candidate)
        errors = [
            issue.message
            for issue in issues
            if issue.severity.value == "ERROR"
        ]
        if errors:
            raise BulkOperationError(
                f"{record.owner}: {errors[0]}"
            )
        return candidate

    def matches(self, model: ZoneModel) -> list[BulkMatch]:
        result: list[BulkMatch] = []
        for view in self.selected(model):
            after = (
                None
                if self.action is BulkAction.DELETE
                else self._replacement(view.record)
            )
            result.append(
                BulkMatch(
                    identifier=view.identifier,
                    before=view.record,
                    after=after,
                )
            )
        return result

    def proposed_records(
        self,
        model: ZoneModel,
    ) -> list[DNSRecord]:
        changes = {
            match.identifier: match.after
            for match in self.matches(model)
        }
        return [
            replacement
            for view in model.record_views
            if not view.deleted
            for replacement in [changes.get(view.identifier, view.record)]
            if replacement is not None
        ]

    def apply(self, model: ZoneModel) -> int:
        matches = self.matches(model)
        if self.action is BulkAction.DELETE:
            changed = model.bulk_delete_by_identifiers(
                [match.identifier for match in matches]
            )
        else:
            changed = model.bulk_replace_by_identifiers(
                {
                    match.identifier: match.after
                    for match in matches
                    if match.after is not None
                }
            )

        if changed:
            model.describe_last_bulk_operation(
                {
                    "query": self.query,
                    "action": self.action.value,
                    "field": self.field,
                    "value": self.value,
                    "matched_count": changed,
                }
            )
        return changed
