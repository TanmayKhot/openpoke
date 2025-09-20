from __future__ import annotations

from pathlib import Path

from .models import TriggerRecord
from .service import TriggerService
from .store import TriggerStore


_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_default_db_path = _DATA_DIR / "triggers.db"
_trigger_store = TriggerStore(_default_db_path)
_trigger_service = TriggerService(_trigger_store)


def get_trigger_service() -> TriggerService:
    return _trigger_service


__all__ = [
    "TriggerRecord",
    "TriggerService",
    "get_trigger_service",
]
