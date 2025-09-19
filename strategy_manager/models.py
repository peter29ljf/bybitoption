"""Data models for strategy management."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class StrategyStatus(str, Enum):
    """Lifecycle status for a trading strategy."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class LevelStatus(str, Enum):
    """Execution status for an individual level."""

    PENDING = "pending"
    WAITING = "waiting"  # waiting for linked trigger
    MONITORING = "monitoring"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MonitorType(str, Enum):
    """Different monitoring hooks for a level."""

    ENTRY = "ENTRY"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"


@dataclass
class LevelExecutionRecord:
    """Execution log for a level transaction."""

    execution_id: str
    monitor_type: MonitorType
    triggered_price: float
    target_price: float
    trigger_direction: str
    side: str
    quantity: str
    order_type: str
    order_price: Optional[str]
    success: bool
    message: str
    order_id: Optional[str] = None
    order_link_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["monitor_type"] = self.monitor_type.value
        return data


@dataclass
class StrategyLevel:
    """One actionable level inside a trading strategy."""

    level_id: str
    option_symbol: str
    side: str  # "buy" or "sell"
    quantity: str
    trigger_type: str  # "immediate", "conditional", "level_close", "existing_position", "btc_price"
    trigger_price: Optional[float]
    take_profit: Optional[float]
    stop_loss: Optional[float]
    order_type: str = "Market"
    limit_price: Optional[float] = None
    status: LevelStatus = LevelStatus.PENDING
    trigger_level_id: Optional[str] = None
    trigger_level_event: Optional[str] = None  # "TAKE_PROFIT", "STOP_LOSS", or None for any
    monitor_task_ids: Dict[str, str] = field(default_factory=dict)  # monitor_type -> task_id
    executions: List[LevelExecutionRecord] = field(default_factory=list)
    last_update: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level_id": self.level_id,
            "option_symbol": self.option_symbol,
            "side": self.side,
            "quantity": self.quantity,
            "trigger_type": self.trigger_type,
            "trigger_price": self.trigger_price,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "status": self.status.value,
            "trigger_level_id": self.trigger_level_id,
            "trigger_level_event": self.trigger_level_event,
            "monitor_task_ids": self.monitor_task_ids,
            "executions": [execution.to_dict() for execution in self.executions],
            "last_update": self.last_update,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyLevel":
        executions = [
            LevelExecutionRecord(
                execution_id=item["execution_id"],
                monitor_type=MonitorType(item["monitor_type"]),
                triggered_price=item["triggered_price"],
                target_price=item["target_price"],
                trigger_direction=item.get("trigger_direction", ""),
                side=item.get("side", ""),
                quantity=item.get("quantity", "0"),
                order_type=item.get("order_type", "Market"),
                order_price=item.get("order_price"),
                success=item.get("success", False),
                message=item.get("message", ""),
                order_id=item.get("order_id"),
                order_link_id=item.get("order_link_id"),
                created_at=item.get("created_at", datetime.utcnow().isoformat() + "Z"),
            )
            for item in data.get("executions", [])
        ]

        return cls(
            level_id=data["level_id"],
            option_symbol=data["option_symbol"],
            side=data["side"],
            quantity=data["quantity"],
            trigger_type=data.get("trigger_type", "immediate"),
            trigger_price=data.get("trigger_price"),
            take_profit=data.get("take_profit"),
            stop_loss=data.get("stop_loss"),
            order_type=data.get("order_type", "Market"),
            limit_price=data.get("limit_price"),
            status=LevelStatus(data.get("status", LevelStatus.PENDING.value)),
            trigger_level_id=data.get("trigger_level_id"),
            trigger_level_event=data.get("trigger_level_event"),
            monitor_task_ids=data.get("monitor_task_ids", {}),
            executions=executions,
            last_update=data.get("last_update", datetime.utcnow().isoformat() + "Z"),
        )


@dataclass
class TradingStrategy:
    """Full strategy definition."""

    strategy_id: str
    name: str
    description: str = ""
    status: StrategyStatus = StrategyStatus.RUNNING
    levels: List[StrategyLevel] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "levels": [level.to_dict() for level in self.levels],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingStrategy":
        return cls(
            strategy_id=data["strategy_id"],
            name=data["name"],
            description=data.get("description", ""),
            status=StrategyStatus(data.get("status", StrategyStatus.RUNNING.value)),
            levels=[StrategyLevel.from_dict(level_data) for level_data in data.get("levels", [])],
            created_at=data.get("created_at", datetime.utcnow().isoformat() + "Z"),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat() + "Z"),
        )


def validate_side(side: str) -> str:
    side_lower = side.lower()
    if side_lower not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")
    return side_lower


def validate_trigger_type(trigger_type: str) -> str:
    value = trigger_type.lower()
    if value not in {"immediate", "conditional", "level_close", "existing_position", "btc_price"}:
        raise ValueError(
            "trigger_type must be 'immediate', 'conditional', 'level_close', 'existing_position', or 'btc_price'"
        )
    return value
