"""ZoneCTL — Transactional DNS Management Toolkit.

Wersja 4.1 wprowadza nową przestrzeń nazw bez zrywania zgodności ze
starszym pakietem ``elkman_dns``. Moduły potomne są w okresie
przejściowym ładowane z jego katalogu; kolejny etap przeniesie ich
fizyczne źródła do ``src/zonectl``.
"""

from __future__ import annotations

from elkman_dns import __path__ as _legacy_path
from elkman_dns import __version__


__path__ = _legacy_path
__all__ = ["__version__"]
