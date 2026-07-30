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

    lines.extend(("", "Etapy:"))

    for step in result.steps:
        marker = "OK" if step.ok else "BŁĄD"
        lines.append(
            f"[{marker:<4}] {step.name}: {step.message}"
        )

        if not step.ok:
            if step.stdout.strip():
                lines.append(
                    f"  stdout: {step.stdout.strip()}"
                )
            if step.stderr.strip():
                lines.append(
                    f"  stderr: {step.stderr.strip()}"
                )

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
