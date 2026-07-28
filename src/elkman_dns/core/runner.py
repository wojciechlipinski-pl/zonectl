from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def run(command: list[str], timeout: int = 10) -> CommandResult:
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(127, "", f"Nie znaleziono polecenia: {command[0]}")
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", f"Przekroczono limit czasu: {' '.join(command)}")
    return CommandResult(proc.returncode, proc.stdout, proc.stderr)
