"""JSON storage helpers for strategy manager."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional, Tuple

from .models import TradingStrategy, StrategyLevel, StrategyStatus, LevelStatus, LevelExecutionRecord

DEFAULT_DATA_DIR = Path("strategy_manager/data")
STRATEGIES_FILE = DEFAULT_DATA_DIR / "strategies.json"
TRADES_FILE = DEFAULT_DATA_DIR / "trades.json"


class JSONStorage:
    """Thread-safe JSON storage for strategies and trades."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._strategies_lock = RLock()
        self._trades_lock = RLock()

        if not STRATEGIES_FILE.exists():
            STRATEGIES_FILE.write_text(json.dumps({"strategies": []}, indent=2, ensure_ascii=False), encoding="utf-8")

        if not TRADES_FILE.exists():
            TRADES_FILE.write_text(json.dumps({"trades": []}, indent=2, ensure_ascii=False), encoding="utf-8")

    # -- strategy helpers -------------------------------------------------
    def load_strategies(self) -> Dict[str, TradingStrategy]:
        with self._strategies_lock:
            raw = json.loads(STRATEGIES_FILE.read_text(encoding="utf-8"))
            result: Dict[str, TradingStrategy] = {}
            for item in raw.get("strategies", []):
                strategy = TradingStrategy.from_dict(item)
                result[strategy.strategy_id] = strategy
            return result

    def save_strategies(self, strategies: Dict[str, TradingStrategy]) -> None:
        with self._strategies_lock:
            payload = {
                "strategies": [strategy.to_dict() for strategy in strategies.values()],
            }
            STRATEGIES_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def upsert_strategy(self, strategy: TradingStrategy) -> None:
        strategies = self.load_strategies()
        strategies[strategy.strategy_id] = strategy
        self.save_strategies(strategies)

    def delete_strategy(self, strategy_id: str) -> bool:
        strategies = self.load_strategies()
        if strategy_id in strategies:
            del strategies[strategy_id]
            self.save_strategies(strategies)
            return True
        return False

    def update_level(self, strategy_id: str, level: StrategyLevel) -> Optional[TradingStrategy]:
        strategies = self.load_strategies()
        strategy = strategies.get(strategy_id)
        if not strategy:
            return None
        level_map = {lvl.level_id: lvl for lvl in strategy.levels}
        level_map[level.level_id] = level
        strategy.levels = list(level_map.values())
        self.upsert_strategy(strategy)
        return strategy

    # -- trade log helpers -----------------------------------------------
    def append_trade(self, record: Dict) -> None:
        with self._trades_lock:
            raw = json.loads(TRADES_FILE.read_text(encoding="utf-8"))
            raw.setdefault("trades", []).append(record)
            TRADES_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_trades(self, limit: Optional[int] = None) -> List[Dict]:
        with self._trades_lock:
            raw = json.loads(TRADES_FILE.read_text(encoding="utf-8"))
            trades: List[Dict] = raw.get("trades", [])
            trades.sort(key=lambda item: item.get("created_at", ""), reverse=True)
            if limit:
                return trades[:limit]
            return trades


storage = JSONStorage()
