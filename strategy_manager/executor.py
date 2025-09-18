"""Execution engine for strategy levels."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from queue import Queue, Empty
from typing import Callable, Dict, Optional

from .models import (
    StrategyLevel,
    MonitorType,
    LevelStatus,
    LevelExecutionRecord,
)
from .storage import storage

logger = logging.getLogger(__name__)


class ExecutionTask:
    def __init__(self, strategy_id: str, level: StrategyLevel, monitor_type: MonitorType, trigger_payload: Dict):
        self.strategy_id = strategy_id
        self.level = level
        self.monitor_type = monitor_type
        self.trigger_payload = trigger_payload


class LevelExecutor:
    """Single threaded executor that processes level execution sequentially."""

    def __init__(self, execute_callback: Callable[[ExecutionTask], Dict]):
        self.execute_callback = execute_callback
        self.queue: "Queue[ExecutionTask]" = Queue()
        self.worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        self._stop_event.clear()
        self.worker = threading.Thread(target=self._run, name="StrategyLevelExecutor", daemon=True)
        self.worker.start()
        logger.info("Level executor started")

    def stop(self) -> None:
        self._stop_event.set()
        if self.worker:
            self.worker.join(timeout=5)
        logger.info("Level executor stopped")

    def enqueue(self, strategy_id: str, level: StrategyLevel, monitor_type: MonitorType, trigger_payload: Dict) -> None:
        task = ExecutionTask(strategy_id, level, monitor_type, trigger_payload)
        self.queue.put(task)
        logger.info("Enqueued level execution task: %s / %s / %s", strategy_id, level.level_id, monitor_type.value)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                task = self.queue.get(timeout=1)
            except Empty:
                continue

            try:
                logger.info(
                    "Processing level execution: strategy=%s level=%s monitor=%s",
                    task.strategy_id,
                    task.level.level_id,
                    task.monitor_type.value,
                )
                task.level.status = LevelStatus.EXECUTING
                storage.update_level(task.strategy_id, task.level)

                result = self.execute_callback(task)
                success = result.get("success", False)

                execution_record = LevelExecutionRecord(
                    execution_id=str(uuid.uuid4()),
                    monitor_type=task.monitor_type,
                    triggered_price=task.trigger_payload.get("trigger_price"),
                    target_price=task.trigger_payload.get("target_price"),
                    trigger_direction=task.trigger_payload.get("trigger_direction", ""),
                    side=task.level.side,
                    quantity=task.level.quantity,
                    order_type=task.level.order_type,
                    order_price=str(task.level.limit_price) if task.level.limit_price else None,
                    success=success,
                    message=result.get("message", ""),
                    order_id=result.get("order_id"),
                    order_link_id=result.get("order_link_id"),
                )

                task.level.executions.append(execution_record)
                task.level.last_update = execution_record.created_at
                status_override = result.get("status")
                if status_override:
                    task.level.status = status_override
                else:
                    task.level.status = LevelStatus.COMPLETED if execution_record.success else LevelStatus.FAILED

                if result.get("cancel_monitors"):
                    task.level.monitor_task_ids = {}
                storage.update_level(task.strategy_id, task.level)

                trade_record = {
                    "strategy_id": task.strategy_id,
                    "level_id": task.level.level_id,
                    "monitor_type": task.monitor_type.value,
                    "option_symbol": task.level.option_symbol,
                    "side": task.level.side,
                    "quantity": task.level.quantity,
                    "order_type": task.level.order_type,
                    "trigger_price": task.trigger_payload.get("trigger_price"),
                    "target_price": task.trigger_payload.get("target_price"),
                    "success": success,
                    "message": execution_record.message,
                    "order_id": execution_record.order_id,
                    "order_link_id": execution_record.order_link_id,
                    "created_at": execution_record.created_at,
                }
                storage.append_trade(trade_record)

            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Execution task failed: %s", exc)
                task.level.status = LevelStatus.FAILED
                storage.update_level(task.strategy_id, task.level)
            finally:
                time.sleep(2)  # enforce spacing between executions
                self.queue.task_done()


executor: Optional[LevelExecutor] = None


def get_executor(callback: Callable[[ExecutionTask], Dict]) -> LevelExecutor:
    global executor
    if executor is None:
        executor = LevelExecutor(callback)
        executor.start()
    return executor
