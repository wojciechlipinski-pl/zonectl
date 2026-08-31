from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class DNSRecord:
    owner: str
    ttl: int | None
    rrclass: str
    rtype: str
    rdata: str
    raw: str

    def relative_owner(self, zone_name: str) -> str:
        zone = zone_name.rstrip(".").casefold()
        owner = self.owner.rstrip(".")
        lowered = owner.casefold()

        if lowered == zone:
            return "@"

        suffix = "." + zone
        if lowered.endswith(suffix):
            return owner[: -len(suffix)]

        return self.owner


class ZoneRecordParser:
    """Parser kanonicznego wyjścia `named-checkzone -D`."""

    IGNORED_PREFIXES = (
        "zone ",
        "loaded serial ",
    )

    @classmethod
    def parse_output(cls, output: str) -> list[DNSRecord]:
        records: list[DNSRecord] = []

        for raw_line in output.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            lowered = line.casefold()

            if lowered == "ok":
                continue

            if any(lowered.startswith(prefix) for prefix in cls.IGNORED_PREFIXES):
                continue

            record = cls.parse_line(line)

            if record is not None:
                records.append(record)

        return records

    @staticmethod
    def parse_line(line: str) -> DNSRecord | None:
        """
        Oczekiwany format kanoniczny:

            owner TTL CLASS TYPE RDATA

        RDATA pozostaje tekstem, dzięki czemu zachowujemy składnię
        rekordów TXT, SOA, MX, SRV, CAA i innych typów.
        """
        fields = line.split(None, 4)

        if len(fields) < 5:
            return None

        owner, ttl_text, rrclass, rtype, rdata = fields

        try:
            ttl = int(ttl_text)
        except ValueError:
            ttl = None

        return DNSRecord(
            owner=owner,
            ttl=ttl,
            rrclass=rrclass.upper(),
            rtype=rtype.upper(),
            rdata=rdata,
            raw=line,
        )
