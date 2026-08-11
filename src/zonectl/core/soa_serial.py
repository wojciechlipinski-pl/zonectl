from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date

from .zone_document import RawLine, RecordNode, ZoneDocument
from .zone_parser import DNSRecord


class SoaSerialError(RuntimeError):
    """Błąd odczytu lub aktualizacji serialu SOA."""


@dataclass(slots=True, frozen=True)
class SoaSerialChange:
    previous: int
    current: int


_MULTILINE_SERIAL_RE = re.compile(
    r"^(?P<prefix>\s*)(?P<serial>\d+)(?P<suffix>\b.*)$"
)

_SINGLE_LINE_SOA_RE = re.compile(
    r"(?P<prefix>\bSOA\b\s+\S+\s+\S+\s+)"
    r"(?P<serial>\d+)"
    r"(?P<suffix>\b)",
    re.IGNORECASE,
)


def next_soa_serial(
    current: int,
    *,
    today: date | None = None,
) -> int:
    """
    Wylicza kolejny serial w formacie RRRRMMDDNN.

    Jeżeli aktualny serial jest starszy niż dzisiejszy:
        RRRRMMDD01

    Jeżeli jest dzisiejszy albo większy:
        aktualny + 1

    Druga reguła gwarantuje monotoniczność również wtedy, gdy w strefie
    znajduje się serial z przyszłą datą lub niestandardowy wysoki serial.
    """
    if current < 0:
        raise SoaSerialError(
            f"Serial SOA nie może być ujemny: {current}"
        )

    current_date = today or date.today()
    daily_base = int(current_date.strftime("%Y%m%d") + "01")

    result = (
        current + 1
        if current >= daily_base
        else daily_base
    )

    if result > 4_294_967_295:
        raise SoaSerialError(
            "Serial SOA przekroczył maksymalną wartość uint32"
        )

    return result


def _replace_record_serial(
    record: DNSRecord,
    new_serial: int,
) -> DNSRecord:
    fields = record.rdata.split()

    # SOA RDATA:
    # MNAME RNAME SERIAL REFRESH RETRY EXPIRE MINIMUM
    if len(fields) < 7:
        raise SoaSerialError(
            "Rekord SOA nie zawiera pełnego RDATA"
        )

    try:
        int(fields[2])
    except ValueError as exc:
        raise SoaSerialError(
            f"Nieprawidłowy serial SOA: {fields[2]}"
        ) from exc

    fields[2] = str(new_serial)

    return replace(
        record,
        rdata=" ".join(fields),
    )


def bump_document_soa_serial(
    document: ZoneDocument,
    *,
    today: date | None = None,
    minimum_current: int | None = None,
) -> SoaSerialChange:
    """
    Podbija serial pierwszego rekordu SOA w ZoneDocument.

    Obsługiwane są:
    - wielowierszowe SOA zachowane jako RawLine,
    - jednowierszowe SOA zapisane jako RecordNode.

    Komentarze i wcięcia wielowierszowego SOA pozostają bez zmian.
    """
    nodes = document.nodes

    for index, node in enumerate(nodes):
        # Jednowierszowy rekord rozpoznany przez parser.
        if isinstance(node, RecordNode):
            if node.record.rtype.upper() != "SOA":
                continue

            fields = node.record.rdata.split()

            if len(fields) < 7:
                raise SoaSerialError(
                    "Rekord SOA nie zawiera pełnego RDATA"
                )

            try:
                previous = int(fields[2])
            except ValueError as exc:
                raise SoaSerialError(
                    f"Nieprawidłowy serial SOA: {fields[2]}"
                ) from exc

            current = next_soa_serial(
                max(previous, minimum_current or previous),
                today=today,
            )

            node.record = _replace_record_serial(
                node.record,
                current,
            )

            # Jeśli rekord był już edytowany, writer i tak go wyrenderuje.
            if node.modified:
                return SoaSerialChange(previous, current)

            # Przy samym podbiciu serialu zachowujemy pierwotny układ linii.
            match = _SINGLE_LINE_SOA_RE.search(node.raw)

            if match is not None:
                node.raw = (
                    node.raw[:match.start("serial")]
                    + str(current)
                    + node.raw[match.end("serial"):]
                )
                return SoaSerialChange(previous, current)

            node.modified = True
            return SoaSerialChange(previous, current)

        if not isinstance(node, RawLine):
            continue

        if re.search(r"\bSOA\b", node.raw, re.IGNORECASE) is None:
            continue

        # SOA może być zapisane w jednej surowej linii.
        single_match = _SINGLE_LINE_SOA_RE.search(node.raw)

        if single_match is not None:
            previous = int(single_match.group("serial"))
            current = next_soa_serial(
                max(previous, minimum_current or previous),
                today=today,
            )

            node.raw = (
                node.raw[:single_match.start("serial")]
                + str(current)
                + node.raw[single_match.end("serial"):]
            )

            return SoaSerialChange(previous, current)

        # Wielowierszowy SOA: serial jest pierwszą liczbą po "(".
        if "(" not in node.raw:
            continue

        for serial_node in nodes[index + 1:]:
            if not isinstance(serial_node, RawLine):
                continue

            match = _MULTILINE_SERIAL_RE.match(
                serial_node.raw
            )

            if match is None:
                continue

            previous = int(match.group("serial"))
            current = next_soa_serial(
                max(previous, minimum_current or previous),
                today=today,
            )

            serial_node.raw = (
                match.group("prefix")
                + str(current)
                + match.group("suffix")
            )

            return SoaSerialChange(previous, current)

    raise SoaSerialError(
        "Nie znaleziono rekordu SOA ani serialu strefy"
    )
