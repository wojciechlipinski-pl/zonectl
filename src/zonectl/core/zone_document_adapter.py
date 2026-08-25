from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace

from .zone_document import RecordNode, ZoneDocument
from .zone_model import ChangeKind, ZoneModel
from .zone_parser import DNSRecord


class ZoneDocumentAdapterError(RuntimeError):
    """Błąd synchronizacji ZoneModel z ZoneDocument."""


@dataclass(slots=True)
class _NodeBinding:
    node: RecordNode
    original_raw: str


class ZoneDocumentAdapter:
    """
    Łączy bufor edycji ZoneModel z bezstratnym ZoneDocument.

    ZoneModel nadal obsługuje logikę zmian dla UI, natomiast adapter
    nanosi te zmiany na węzły dokumentu przed użyciem ZoneWriter.

    Istniejące rekordy są wiązane z RecordNode według ich kolejności
    podczas tworzenia adaptera. Dzięki temu poprawnie obsługiwane są
    również identyczne rekordy występujące więcej niż raz.
    """

    def __init__(
        self,
        document: ZoneDocument,
        model: ZoneModel,
    ) -> None:
        self.document = document
        self.model = model

        self._bindings: dict[int, _NodeBinding] = {}
        self._added_nodes: dict[int, RecordNode] = {}

        self._bind_existing_records()

    def _bind_existing_records(self) -> None:
        nodes = list(self.document.iter_record_nodes())

        original_views = [
            view
            for view in self.model.record_views
            if view.change_kind is not ChangeKind.ADD
        ]

        if len(nodes) != len(original_views):
            raise ZoneDocumentAdapterError(
                "Liczba rekordów ZoneDocument i ZoneModel jest różna: "
                f"{len(nodes)} != {len(original_views)}"
            )

        for node, view in zip(nodes, original_views, strict=True):
            if node.record != view.record:
                raise ZoneDocumentAdapterError(
                    "Kolejność lub zawartość rekordów ZoneDocument "
                    "nie odpowiada rekordom ZoneModel"
                )

            self._bindings[view.identifier] = _NodeBinding(
                node=node,
                original_raw=node.raw,
            )

    def apply(self) -> ZoneDocument:
        """
        Nanieś bieżące zmiany modelu na dokument.

        Metoda może być wykonywana wielokrotnie. Dodane rekordy nie będą
        ponownie dopisywane, a cofnięte zmiany zostaną wyzerowane.
        """
        active_identifiers: set[int] = set()

        for view in self.model.record_views:
            active_identifiers.add(view.identifier)

            if view.change_kind is ChangeKind.ADD:
                self._apply_add(
                    identifier=view.identifier,
                    record=view.record,
                )
                continue

            binding = self._bindings.get(view.identifier)

            if binding is None:
                raise ZoneDocumentAdapterError(
                    "Brak powiązania dokumentu dla rekordu "
                    f"{view.identifier}"
                )

            node = binding.node

            if view.change_kind is ChangeKind.DELETE:
                node.deleted = True
                node.modified = False
                continue

            node.deleted = False

            if view.change_kind is ChangeKind.MODIFY:
                record = view.record

                # Podgląd/dry-run może już podbić serial SOA w dokumencie.
                # Ponowne renderowanie nie może cofnąć go do wartości z
                # modelu, który celowo przechowuje zmianę operatora sprzed
                # automatycznego podbicia serialu.
                if (
                    node.modified
                    and node.record.rtype.upper() == "SOA"
                    and record.rtype.upper() == "SOA"
                ):
                    current_fields = node.record.rdata.split()
                    proposed_fields = record.rdata.split()
                    if len(current_fields) >= 7 and len(proposed_fields) >= 7:
                        proposed_fields[2] = current_fields[2]
                        record = replace(
                            record,
                            rdata=" ".join(proposed_fields),
                        )

                node.record = record
                node.modified = True
            else:
                # Zachowaj zmianę serialu przygotowaną przez sesję między
                # kolejnymi wywołaniami render_candidate().
                if not (
                    node.modified
                    and node.record.rtype.upper() == "SOA"
                ):
                    node.modified = False

        self._remove_abandoned_added_nodes(active_identifiers)

        return self.document

    def _apply_add(
        self,
        identifier: int,
        record: DNSRecord,
    ) -> None:
        node = self._added_nodes.get(identifier)

        if node is None:
            node = RecordNode(
                record=record,
                raw="",
                modified=True,
                deleted=False,
            )

            self.document.nodes.append(node)
            self._added_nodes[identifier] = node
            return

        node.record = record
        node.modified = True
        node.deleted = False

    def _remove_abandoned_added_nodes(
        self,
        active_identifiers: set[int],
    ) -> None:
        abandoned = [
            identifier
            for identifier in self._added_nodes
            if identifier not in active_identifiers
        ]

        for identifier in abandoned:
            node = self._added_nodes.pop(identifier)

            try:
                self.document.nodes.remove(node)
            except ValueError:
                pass

    def discard(self) -> ZoneDocument:
        """
        Przywróć dokument do stanu sprzed zmian modelu.

        Powinno być wywołane razem z ZoneModel.discard().
        """
        for binding in self._bindings.values():
            node = binding.node
            node.deleted = False
            node.modified = False

        for node in tuple(self._added_nodes.values()):
            try:
                self.document.nodes.remove(node)
            except ValueError:
                pass

        self._added_nodes.clear()

        return self.document
