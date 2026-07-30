"""Widoki i komponenty obsługi rekordów DNS."""

from .editor import RecordEditor
from .renderer import RecordRenderer

__all__ = ["RecordController", "RecordEditor", "RecordRenderer"]
from .new_record import NewRecordDialog, RECORD_TYPES
from .controller import RecordController
