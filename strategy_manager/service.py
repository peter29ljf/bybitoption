"""Strategy service orchestrating storage, monitor client and execution."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from flask import current_app

from .executor import get_executor, ExecutionTask
from .models import (
    TradingStrategy,
    StrategyLevel,
    StrategyStatus,
    LevelStatus,
    MonitorType,
)
from .monitor_client import monitor_client

BTC_SPOT_SYMBOL = "BTCUSDT"
from .storage import storage

logger = logging.getLogger(__name__)


class StrategyService:
    def __init__(self):
        self._strategies: Dict[str, TradingStrategy] = storage.load_strategies()
        self.executor = get_executor(self._execute_level)
        self.app = None

    def init_app(self, app):
        self.app = app
        app.extensions["strategy_service"] = self
        app.config.setdefault("STRATEGY_WEBHOOK_BASE", app.config.get("EXTERNAL_BASE_URL", "http://localhost:8080"))
        monitor_client.base_url = app.config.get("PRICE_MONITOR_BASE", monitor_client.base_url)

    # -- strategy CRUD ---------------------------------------------------
    def list_strategies(self) -> List[Dict]:
        self._refresh()
        return [strategy.to_dict() for strategy in self._strategies.values()]

    def get_strategy(self, strategy_id: str) -> Optional[TradingStrategy]:
        self._refresh()
        return self._strategies.get(strategy_id)

    def create_strategy(self, payload: Dict) -> TradingStrategy:
        strategy_id = payload.get("strategy_id") or str(uuid.uuid4())
        levels = [self._build_level(level_data) for level_data in payload.get("levels", [])]
        strategy = TradingStrategy(
            strategy_id=strategy_id,
            name=payload["name"],
            description=payload.get("description", ""),
            status=StrategyStatus(payload.get("status", StrategyStatus.RUNNING.value)),
            levels=levels,
        )
        storage.upsert_strategy(strategy)
        self._strategies[strategy.strategy_id] = strategy
        self._sync_monitors(strategy)
        return strategy

    def update_strategy(self, strategy_id: str, payload: Dict) -> Optional[TradingStrategy]:
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return None

        strategy.name = payload.get("name", strategy.name)
        strategy.description = payload.get("description", strategy.description)
        strategy.status = StrategyStatus(payload.get("status", strategy.status.value))
        existing_map = {lvl.level_id: lvl for lvl in strategy.levels}
        new_levels: List[StrategyLevel] = []

        for level_data in payload.get("levels", []):
            level_id = level_data.get("level_id")
            existing_level = existing_map.get(level_id) if level_id else None
            new_level = self._build_level(level_data, existing_level)
            if existing_level and existing_level.monitor_task_ids:
                new_level.monitor_task_ids = existing_level.monitor_task_ids
                new_level.executions = existing_level.executions
                new_level.status = existing_level.status
            new_levels.append(new_level)

        removed_levels = set(existing_map.keys()) - {lvl.level_id for lvl in new_levels if lvl.level_id}
        for removed_id in removed_levels:
            self._cancel_level_monitors(existing_map[removed_id])

        strategy.levels = new_levels
        strategy.updated_at = datetime.utcnow().isoformat() + "Z"
        storage.upsert_strategy(strategy)
        self._strategies[strategy.strategy_id] = strategy
        self._sync_monitors(strategy)
        return strategy

    def delete_strategy(self, strategy_id: str) -> bool:
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return False
        for level in strategy.levels:
            self._cancel_level_monitors(level)
        storage.delete_strategy(strategy_id)
        self._strategies.pop(strategy_id, None)
        return True

    def pause_strategy(self, strategy_id: str) -> Optional[TradingStrategy]:
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return None
        strategy.status = StrategyStatus.PAUSED
        strategy.updated_at = datetime.utcnow().isoformat() + "Z"
        storage.upsert_strategy(strategy)
        self._strategies[strategy_id] = strategy
        for level in strategy.levels:
            self._cancel_level_monitors(level)
            if level.status == LevelStatus.MONITORING:
                level.status = LevelStatus.PENDING
        storage.upsert_strategy(strategy)
        return strategy

    def resume_strategy(self, strategy_id: str) -> Optional[TradingStrategy]:
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return None
        strategy.status = StrategyStatus.RUNNING
        strategy.updated_at = datetime.utcnow().isoformat() + "Z"
        storage.upsert_strategy(strategy)
        self._strategies[strategy_id] = strategy
        self._sync_monitors(strategy)
        return strategy

    def stop_strategy(self, strategy_id: str) -> Optional[TradingStrategy]:
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return None
        strategy.status = StrategyStatus.STOPPED
        strategy.updated_at = datetime.utcnow().isoformat() + "Z"
        for level in strategy.levels:
            self._cancel_level_monitors(level)
            if level.status not in (LevelStatus.COMPLETED, LevelStatus.FAILED):
                level.status = LevelStatus.CANCELLED
        storage.upsert_strategy(strategy)
        self._strategies[strategy_id] = strategy
        return strategy

    # -- monitoring ------------------------------------------------------
    def handle_webhook(self, payload: Dict) -> Optional[StrategyLevel]:
        strategy_id = payload.get("strategy_id")
        level_id = payload.get("level_id")
        monitor_type = MonitorType(payload.get("monitor_type"))
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            logger.error("Webhook strategy not found: %s", strategy_id)
            return None
        level = next((lvl for lvl in strategy.levels if lvl.level_id == level_id), None)
        if not level:
            logger.error("Webhook level not found: %s/%s", strategy_id, level_id)
            return None

        trigger_payload = {
            "target_price": payload.get("target_price"),
            "trigger_price": payload.get("trigger_price"),
            "trigger_direction": payload.get("trigger_direction"),
        }

        if strategy.status != StrategyStatus.RUNNING:
            logger.info("Strategy %s not running, ignore webhook", strategy_id)
            return level

        if level.status in (LevelStatus.COMPLETED, LevelStatus.FAILED, LevelStatus.CANCELLED):
            logger.info("Level already finished, ignore webhook: %s", level.level_id)
            return level

        self.executor.enqueue(strategy.strategy_id, level, monitor_type, trigger_payload)
        return level

    def enqueue_immediate_levels(self, strategy: TradingStrategy) -> None:
        for level in strategy.levels:
            if level.trigger_type == "immediate" and level.status in (LevelStatus.PENDING, LevelStatus.MONITORING):
                self.executor.enqueue(strategy.strategy_id, level, MonitorType.ENTRY, {
                    "target_price": level.limit_price or 0,
                    "trigger_price": level.limit_price,
                    "trigger_direction": "immediate",
                })

    # -- private helpers -------------------------------------------------
    def _refresh(self) -> None:
        self._strategies = storage.load_strategies()

    def _build_level(self, data: Dict, existing_level: Optional[StrategyLevel] = None) -> StrategyLevel:
        level_id = data.get("level_id") or (existing_level.level_id if existing_level else str(uuid.uuid4()))
        merged_data = {**(existing_level.to_dict() if existing_level else {}), **data, "level_id": level_id}
        if merged_data.get("trigger_level_event"):
            merged_data["trigger_level_event"] = merged_data["trigger_level_event"].upper()
        level = StrategyLevel.from_dict(merged_data)
        return level

    def _trigger_linked_levels(self, strategy_id: str, completed_level_id: str, monitor: MonitorType) -> None:
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return
        updated = False
        for level in strategy.levels:
            if level.trigger_type != "level_close":
                continue
            if level.trigger_level_id != completed_level_id:
                continue
            if level.trigger_level_event and level.trigger_level_event != monitor.value:
                continue
            if level.status in (LevelStatus.COMPLETED, LevelStatus.FAILED, LevelStatus.CANCELLED, LevelStatus.EXECUTING, LevelStatus.MONITORING):
                continue
            level.status = LevelStatus.MONITORING
            updated = True
            trigger_payload = {
                "target_price": level.limit_price,
                "trigger_price": level.limit_price,
                "trigger_direction": monitor.value.lower(),
            }
            self.executor.enqueue(strategy_id, level, MonitorType.ENTRY, trigger_payload)
        if updated:
            storage.upsert_strategy(strategy)
            self._strategies[strategy_id] = strategy

    def _ensure_post_entry_monitors(self, strategy_id: str, level: StrategyLevel) -> None:
        definitions = self._build_closing_monitors(level)
        if not definitions:
            return
        webhook_url = self._webhook_url()
        try:
            task_ids = monitor_client.sync_level_tasks(
                strategy_id,
                level.level_id,
                self._normalize_symbol(level.option_symbol),
                definitions,
                webhook_url,
            )
            for monitor, task_id in task_ids.items():
                level.monitor_task_ids[monitor.value] = task_id
            storage.update_level(strategy_id, level)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to create post-entry monitors for level %s", level.level_id)


    def _build_closing_monitors(self, level: StrategyLevel) -> List[Dict]:
        definitions: List[Dict] = []
        if level.take_profit and MonitorType.TAKE_PROFIT.value not in level.monitor_task_ids:
            definitions.append({
                "monitor_type": MonitorType.TAKE_PROFIT.value,
                "target_price": level.take_profit,
            })
        if level.stop_loss and MonitorType.STOP_LOSS.value not in level.monitor_task_ids:
            definitions.append({
                "monitor_type": MonitorType.STOP_LOSS.value,
                "target_price": level.stop_loss,
            })
        return definitions

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if not symbol:
            return symbol
        upper = symbol.upper()
        if upper.endswith('-USDT') or upper.endswith('-USD') or upper.endswith('-USDC'):
            return upper
        return '{}-USDT'.format(upper)

    def _cancel_level_monitors(self, level: StrategyLevel) -> None:
        for task_id in level.monitor_task_ids.values():
            try:
                monitor_client.delete_task(task_id)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed to delete monitor task %s", task_id)
        level.monitor_task_ids = {}

    def _sync_monitors(self, strategy: TradingStrategy) -> None:
        if strategy.status != StrategyStatus.RUNNING:
            logger.info("Strategy %s not running, skip monitor sync", strategy.strategy_id)
            return

        webhook_url = self._webhook_url()
        for level in strategy.levels:
            if level.status in (LevelStatus.COMPLETED, LevelStatus.FAILED, LevelStatus.CANCELLED):
                continue

            monitor_definitions: List[Dict] = []
            executions = getattr(level, "executions", [])
            entry_executed = any(
                getattr(exec, "monitor_type", None) == MonitorType.ENTRY and getattr(exec, "success", False)
                for exec in executions
            )

            if level.trigger_type == "conditional" and level.trigger_price and not entry_executed:
                monitor_definitions.append({
                    "monitor_type": MonitorType.ENTRY.value,
                    "target_price": level.trigger_price,
                    "metadata": {
                        "side": level.side,
                        "quantity": level.quantity,
                    },
                })
                level.status = LevelStatus.MONITORING
            elif level.trigger_type == "btc_price" and level.trigger_price and not entry_executed:
                spot_symbol = self._spot_symbol_for_level(level)
                if not spot_symbol:
                    logger.warning(
                        "Level %s configured for btc_price trigger but option symbol %s is not BTC-based",
                        level.level_id,
                        level.option_symbol,
                    )
                    level.status = LevelStatus.PENDING
                else:
                    monitor_definitions.append({
                        "monitor_type": MonitorType.ENTRY.value,
                        "target_price": level.trigger_price,
                        "metadata": {
                            "side": level.side,
                            "quantity": level.quantity,
                            "trigger_basis": "btc_spot",
                        },
                        "instrument_type": "spot",
                        "monitor_symbol": spot_symbol,
                    })
                    level.status = LevelStatus.MONITORING
            elif level.trigger_type == "immediate" and not entry_executed:
                level.status = LevelStatus.MONITORING
                self.executor.enqueue(
                    strategy.strategy_id,
                    level,
                    MonitorType.ENTRY,
                    {
                        "target_price": level.limit_price,
                        "trigger_price": level.limit_price,
                        "trigger_direction": "immediate",
                    },
                )
            elif level.trigger_type == "existing_position":
                level.status = LevelStatus.MONITORING
            elif level.trigger_type == "level_close":
                if not level.trigger_level_id:
                    level.status = LevelStatus.PENDING
                elif not entry_executed:
                    level.status = LevelStatus.WAITING
                else:
                    monitor_definitions.extend(self._build_closing_monitors(level))

            if level.trigger_type != "level_close":
                if level.take_profit:
                    monitor_definitions.append({
                        "monitor_type": MonitorType.TAKE_PROFIT.value,
                        "target_price": level.take_profit,
                    })

                if level.stop_loss:
                    monitor_definitions.append({
                        "monitor_type": MonitorType.STOP_LOSS.value,
                        "target_price": level.stop_loss,
                    })

            if monitor_definitions:
                try:
                    if level.monitor_task_ids:
                        self._cancel_level_monitors(level)
                    task_ids = monitor_client.sync_level_tasks(
                        strategy.strategy_id,
                        level.level_id,
                        self._normalize_symbol(level.option_symbol),
                        monitor_definitions,
                        webhook_url,
                    )
                    level.monitor_task_ids = {monitor.value: task_id for monitor, task_id in task_ids.items()}
                except Exception:  # pylint: disable-broad-except
                    logger.exception("Failed to sync monitor tasks for level %s", level.level_id)

            level.last_update = datetime.utcnow().isoformat() + "Z"

        strategy.updated_at = datetime.utcnow().isoformat() + "Z"
        storage.upsert_strategy(strategy)
        self._strategies[strategy.strategy_id] = strategy

    @staticmethod
    def _spot_symbol_for_level(level: StrategyLevel) -> Optional[str]:
        symbol = (level.option_symbol or "").upper()
        if symbol.startswith("BTC"):
            return BTC_SPOT_SYMBOL
        return None

    def _execute_level(self, task: ExecutionTask) -> Dict:
        if not self.app:
            raise RuntimeError("StrategyService not initialized with app")

        with self.app.app_context():
            trader = current_app.config.get("STRATEGY_TRADER")
        if not trader:
            raise RuntimeError("Strategy trader not configured")

        level = task.level
        order_type = level.order_type or "Market"
        price = str(level.limit_price) if level.limit_price and order_type != "Market" else None
        symbol = self._normalize_symbol(level.option_symbol)

        side_lower = level.side.lower()
        monitor = task.monitor_type
        trade_side = side_lower

        if monitor in (MonitorType.TAKE_PROFIT, MonitorType.STOP_LOSS):
            trade_side = 'sell' if side_lower == 'buy' else 'buy'

        if trade_side == 'buy':
            result = trader.buy_option(
                symbol=symbol,
                quantity=level.quantity,
                order_type=order_type,
                price=price,
                auto_confirm=True,
            )
        else:
            result = trader.sell_option(
                symbol=symbol,
                quantity=level.quantity,
                order_type=order_type,
                price=price,
                auto_confirm=True,
            )

        success = result.get("success", False)

        message = result.get("message")
        if result.get("cancelled"):
            message = message or "Order cancelled"
        elif not success:
            message = message or result.get("error", "Unknown error")
        order_id = result.get("order_id")
        order_link_id = result.get("order_link_id")

        if monitor == MonitorType.ENTRY:
            if success:
                level.monitor_task_ids.pop(MonitorType.ENTRY.value, None)
                if level.take_profit or level.stop_loss:
                    level.status = LevelStatus.MONITORING
                    self._ensure_post_entry_monitors(task.strategy_id, level)
                else:
                    level.status = LevelStatus.COMPLETED
                    self._cancel_level_monitors(level)
            else:
                level.status = LevelStatus.FAILED
        else:
            if success:
                level.status = LevelStatus.COMPLETED
                self._cancel_level_monitors(level)
                self._trigger_linked_levels(task.strategy_id, level.level_id, monitor)
            else:
                level.status = LevelStatus.FAILED

        return {
            "success": success,
            "message": message,
            "status": level.status,
            "cancel_monitors": success and monitor != MonitorType.ENTRY,
            "order_id": order_id,
            "order_link_id": order_link_id,
        }

    def _webhook_url(self) -> str:
        # Assume the Flask app knows its external URL or running on localhost
        if not self.app:
            raise RuntimeError("StrategyService not initialized with app")
        base_url = self.app.config.get("STRATEGY_WEBHOOK_BASE", "http://localhost:8080")
        return f"{base_url.rstrip('/')}/api/strategies/webhook"


strategy_service = StrategyService()
