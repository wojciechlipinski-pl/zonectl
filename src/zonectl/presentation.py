from __future__ import annotations

from .core.transaction import TransactionResult


def transaction_lines(
    result: TransactionResult,
) -> list[str]:
    """Zbuduj wspólną prezentację wyniku transakcji dla CLI i TUI."""
    lines = [
        f"Transakcja: {result.transaction_id}",
        f"Strefa:     {result.zone}",
        f"Status:     {result.status}",
        f"Commit:     {'TAK' if result.committed else 'NIE'}",
        f"Rollback:   {'TAK' if result.rolled_back else 'NIE'}",
    ]

    if result.backup:
        lines.append(f"Backup:     {result.backup}")

    bulk_operations = result.metadata.get("bulk_operations", [])
    if isinstance(bulk_operations, list) and bulk_operations:
        lines.extend(("", "Operacje masowe:"))
        for operation in bulk_operations:
            if not isinstance(operation, dict):
                continue
            action = str(operation.get("action", "?"))
            field = operation.get("field")
            value = operation.get("value")
            assignment = f" {field}={value}" if action == "SET" and field else ""
            lines.append(
                "  "
                f"SELECT {operation.get('query', '?')} "
                f"{action}{assignment} "
                f"({operation.get('matched_count', 0)} rekordów)"
            )

    lines.extend(("", "Etapy:"))

    for step in result.steps:
        marker = "OK" if step.ok else "BŁĄD"
        lines.append(f"[{marker:<4}] {step.name}: {step.message}")

        if not step.ok:
            if step.stdout.strip():
                lines.append(f"  stdout: {step.stdout.strip()}")
            if step.stderr.strip():
                lines.append(f"  stderr: {step.stderr.strip()}")

    return lines


def transaction_title(
    result: TransactionResult,
) -> str:
    """Zwróć wspólny tytuł wyniku transakcji."""
    return f"Wynik transakcji: {result.status}"


def transaction_exit_code(
    result: TransactionResult,
) -> int:
    """Przełóż wynik transakcji na kod procesu CLI."""
    return 0 if result.ok else 1
