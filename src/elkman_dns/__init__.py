"""Zgodna nazwa historyczna; nowy kod powinien używać pakietu zonectl."""

from __future__ import annotations

from zonectl import __path__, __version__

__all__ = ["__version__"]
