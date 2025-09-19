"""
数据模型
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime
import json

@dataclass
class OptionInfo:
    """期权信息"""
    symbol: str          # 期权合约符号，如 BTC-17JAN25-100000-C
    base_coin: str       # 基础币种，如 BTC
    strike_price: float  # 执行价格
    expiry_date: str     # 到期日期
    option_type: str     # 期权类型 Call/Put
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class MonitorTask:
    """监控任务"""
    task_id: str                    # 任务唯一编号
    option_info: OptionInfo         # 期权信息
    monitor_symbol: str             # 实际监控的Symbol（期权或现货）
    target_price: float             # 目标价格
    webhook_url: str                # 接收webhook的网址
    created_at: datetime            # 创建时间
    expires_at: datetime            # 过期时间
    current_price: Optional[float] = None    # 当前价格
    previous_price: Optional[float] = None   # 上一次价格（用于判断穿越方向）
    status: str = "active"          # 任务状态: active, triggered, expired, cancelled
    triggered_at: Optional[datetime] = None  # 触发时间
    strategy_id: Optional[str] = None        # 关联策略
    level_id: Optional[str] = None           # 关联level
    monitor_type: Optional[str] = None       # ENTRY/TAKE_PROFIT/STOP_LOSS
    metadata: Optional[Dict[str, Any]] = None
    monitor_instrument: str = "option"  # 监控标的类型: option/spot

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # 处理datetime序列化
        result['created_at'] = self.created_at.isoformat()
        result['expires_at'] = self.expires_at.isoformat()
        if self.triggered_at:
            result['triggered_at'] = self.triggered_at.isoformat()
        # 处理嵌套对象
        result['option_info'] = self.option_info.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MonitorTask':
        """从字典创建监控任务"""
        # 处理datetime反序列化
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        if data.get('triggered_at'):
            data['triggered_at'] = datetime.fromisoformat(data['triggered_at'])
        
        # 处理嵌套对象
        option_data = data.pop('option_info')
        data['option_info'] = OptionInfo(**option_data)

        # 兼容旧数据
        data.setdefault('monitor_instrument', 'option')
        data.setdefault('monitor_symbol', data['option_info'].symbol)

        return cls(**data)

@dataclass
class WebhookData:
    """Webhook发送数据"""
    task_id: str                    # 任务编号
    option_symbol: str              # 期权合约符号
    target_price: float             # 目标价格
    triggered_price: float          # 触发时的价格
    previous_price: float           # 之前的价格
    trigger_direction: str          # 触发方向: up_cross(上穿) 或 down_cross(下穿)
    triggered_at: str               # 触发时间
    strategy_id: Optional[str] = None
    level_id: Optional[str] = None
    monitor_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    monitor_symbol: Optional[str] = None
    monitor_instrument: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class PriceUpdate:
    """价格更新数据"""
    symbol: str
    price: float
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result
