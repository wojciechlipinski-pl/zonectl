"""Stan, sortowanie i filtrowanie widoku rekordów DNS."""

from __future__ import annotations

from collections.abc import Sequence
import re

from zonectl.core.zone_model import ZoneModel, ZoneRecordView


def natural_name_key(value: str) -> tuple[tuple[int, object], ...]:
    """Sortuj cyfry według wartości, a tekst bez rozróżniania liter."""
    if value == "@":
        return ((-1, ""),)

    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", value)
        if part
    )


class RecordController:
    """Zarządza prezentacją rekordów bez zależności od curses."""

    SORT_NAMES: tuple[str, ...] = (
        "Nazwa",
        "Typ",
        "TTL",
    )

    def __init__(
        self,
        model: ZoneModel,
        zone_name: str,
    ) -> None:
        self.model = model
        self.zone_name = zone_name.rstrip(".")

        self.selected = 0
        self.offset = 0
        self.sort_mode = 0
        self.search_query = ""

    @property
    def sort_name(self) -> str:
        return self.SORT_NAMES[self.sort_mode]

    def cycle_sort(self) -> None:
        self.sort_mode = (
            self.sort_mode + 1
        ) % len(self.SORT_NAMES)

        self.selected = 0
        self.offset = 0

    def set_search(self, value: str) -> None:
        self.search_query = value.strip()
        self.selected = 0
        self.offset = 0

    def clear_search(self) -> None:
        self.search_query = ""
        self.selected = 0
        self.offset = 0

    def _name_key(
        self,
        view: ZoneRecordView,
    ) -> tuple[tuple[tuple[int, object], ...], str, str, int]:
        record = view.record

        return (
            natural_name_key(record.relative_owner(self.zone_name)),
            record.rtype.casefold(),
            record.rdata.casefold(),
            view.identifier,
        )

    def _type_key(
        self,
        view: ZoneRecordView,
    ) -> tuple[str, tuple[tuple[int, object], ...], str, int]:
        record = view.record

        return (
            record.rtype.casefold(),
            natural_name_key(record.relative_owner(self.zone_name)),
            record.rdata.casefold(),
            view.identifier,
        )

    def _ttl_key(
        self,
        view: ZoneRecordView,
    ) -> tuple[bool, int, tuple[tuple[int, object], ...], str, int]:
        record = view.record

        return (
            record.ttl is None,
            record.ttl or 0,
            natural_name_key(record.relative_owner(self.zone_name)),
            record.rtype.casefold(),
            view.identifier,
        )

    def ordered_views(self) -> list[ZoneRecordView]:
        views = list(self.model.record_views)

        if self.sort_mode == 1:
            result = sorted(
                views,
                key=self._type_key,
            )
        elif self.sort_mode == 2:
            result = sorted(
                views,
                key=self._ttl_key,
            )
        else:
            result = sorted(
                views,
                key=self._name_key,
            )

        query = self.search_query.casefold()

        if not query:
            return result

        filtered: list[ZoneRecordView] = []

        for view in result:
            record = view.record
            owner = record.relative_owner(self.zone_name)
            ttl = "" if record.ttl is None else str(record.ttl)

            searchable = " ".join(
                (
                    view.marker,
                    owner,
                    record.rtype,
                    ttl,
                    record.rdata,
                )
            ).casefold()

            if query in searchable:
                filtered.append(view)

        return filtered

    def clamp_selection(
        self,
        views: Sequence[ZoneRecordView],
        visible_rows: int,
    ) -> None:
        if not views:
            self.selected = 0
            self.offset = 0
            return

        self.selected = min(
            self.selected,
            len(views) - 1,
        )

        if self.selected < self.offset:
            self.offset = self.selected

        if self.selected >= self.offset + visible_rows:
            self.offset = (
                self.selected
                - visible_rows
                + 1
            )

        self.offset = max(0, self.offset)

    def move(
        self,
        delta: int,
        views: Sequence[ZoneRecordView],
    ) -> None:
        if not views:
            self.selected = 0
            return

        self.selected = min(
            max(0, self.selected + delta),
            len(views) - 1,
        )

    def current(
        self,
        views: Sequence[ZoneRecordView],
    ) -> ZoneRecordView | None:
        if not views:
            return None

        if self.selected < 0 or self.selected >= len(views):
            return None

        return views[self.selected]

    def select_identifier(
        self,
        views: Sequence[ZoneRecordView],
        identifier: int,
    ) -> bool:
        for index, view in enumerate(views):
            if view.identifier == identifier:
                self.selected = index
                return True

        return False
