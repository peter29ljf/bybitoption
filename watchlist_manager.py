"""Persist watchlist items to disk."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import List, Dict


WATCHLIST_FILE = Path("data/watchlist.json")


class WatchlistManager:
    def __init__(self) -> None:
        self._lock = RLock()
        WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Dict]:
        with self._lock:
            if WATCHLIST_FILE.exists():
                try:
                    data = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        return data
                except (json.JSONDecodeError, OSError):
                    return []
            return []

    def save(self, items: List[Dict]) -> None:
        with self._lock:
            WATCHLIST_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    def clear(self) -> None:
        with self._lock:
            if WATCHLIST_FILE.exists():
                WATCHLIST_FILE.unlink()


watchlist_manager = WatchlistManager()
