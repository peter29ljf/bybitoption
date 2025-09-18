"""Manage persistent application settings."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict

from config import Config


SETTINGS_DIR = Path("settings_manager/data")
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


@dataclass
class AppSettings:
    api_key: str = ""
    api_secret: str = ""
    is_testnet: bool = True
    price_monitor_base: str = "http://localhost:8888"
    strategy_webhook_base: str = "http://localhost:8080"

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "AppSettings":
        return cls(
            api_key=data.get("api_key", ""),
            api_secret=data.get("api_secret", ""),
            is_testnet=bool(data.get("is_testnet", True)),
            price_monitor_base=data.get("price_monitor_base", "http://localhost:8888"),
            strategy_webhook_base=data.get("strategy_webhook_base", "http://localhost:8080"),
        )


class SettingsManager:
    def __init__(self) -> None:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        self._settings = self._load_file()

    def _load_file(self) -> AppSettings:
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                return AppSettings.from_dict(data)
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        # Fallback to Config defaults
        return AppSettings(
            api_key=Config.BYBIT_API_KEY,
            api_secret=Config.BYBIT_API_SECRET,
            is_testnet=Config.BYBIT_TESTNET,
            price_monitor_base=Config.PRICE_MONITOR_BASE,
            strategy_webhook_base=Config.STRATEGY_WEBHOOK_BASE,
        )

    def get_settings(self) -> AppSettings:
        return self._settings

    def save_settings(self, settings: AppSettings) -> None:
        self._settings = settings
        SETTINGS_FILE.write_text(
            json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def update(self, payload: Dict) -> AppSettings:
        data = self._settings.to_dict()
        data.update(payload)
        settings = AppSettings.from_dict(data)
        self.save_settings(settings)
        return settings


settings_manager = SettingsManager()
