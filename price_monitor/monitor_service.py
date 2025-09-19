"""价格监控服务"""
import asyncio
import json
import logging
from contextlib import suppress
import aiohttp
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
from .models import MonitorTask, PriceUpdate, WebhookData
from .storage import TaskStorage, get_storage
from .websocket_client import BybitWebSocketClient
from .config import MonitorConfig

logger = logging.getLogger(__name__)

class PriceMonitorService:
    """价格监控服务"""
    
    def __init__(self):
        self.storage: TaskStorage = get_storage()
        self.ws_client = BybitWebSocketClient()
        self.active_tasks: Dict[str, MonitorTask] = {}
        self.monitored_option_symbols: Set[str] = set()
        self.monitored_spot_symbols: Set[str] = set()
        self._spot_task: Optional[asyncio.Task] = None
        self.running = False
        
        # 设置价格更新回调
        self.ws_client.set_price_callback(self._on_price_update)
        self._snapshot_active_tasks()
    
    async def start(self):
        """启动监控服务"""
        logger.info("启动价格监控服务...")
        
        try:
            # 连接WebSocket
            await self.ws_client.connect()

            self.running = True

            # 加载现有的活跃任务
            await self._load_active_tasks()
            
            # 启动定期任务
            asyncio.create_task(self._periodic_cleanup())
            logger.info("价格监控服务启动成功")
            
        except Exception as e:
            logger.error(f"启动监控服务失败: {e}")
            raise
    
    async def stop(self):
        """停止监控服务"""
        logger.info("停止价格监控服务...")
        self.running = False

        # 断开WebSocket连接
        await self.ws_client.disconnect()

        if self._spot_task:
            self._spot_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._spot_task
            self._spot_task = None

        self.monitored_option_symbols = set()
        self.monitored_spot_symbols = set()

        logger.info("价格监控服务已停止")
    
    async def add_monitor_task(self, task: MonitorTask) -> bool:
        """添加监控任务"""
        success = False
        try:
            # 保存任务到存储
            if not self.storage.save_task(task):
                logger.error(f"保存任务失败: {task.task_id}")
                return False

            # 添加到活跃任务
            self.active_tasks[task.task_id] = task

            # 更新监控的符号集合
            await self._update_monitored_symbols()

            logger.info(
                "添加监控任务: %s, 标的: %s (%s), 目标价格: %s",
                task.task_id,
                task.monitor_symbol,
                task.monitor_instrument,
                task.target_price,
            )
            success = True
            return True

        except Exception as e:
            logger.error(f"添加监控任务失败: {e}")
            return False

        finally:
            if success:
                self._snapshot_active_tasks()
    
    async def remove_monitor_task(self, task_id: str) -> bool:
        """移除监控任务"""
        try:
            # 从活跃任务中移除
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

            # 从存储中删除
            self.storage.delete_task(task_id)

            # 更新监控的符号集合
            await self._update_monitored_symbols()

            logger.info("移除监控任务: %s", task_id)
            return True

        except Exception as e:
            logger.error(f"移除监控任务失败: {e}")
            return False

        finally:
            self._snapshot_active_tasks()
    
    async def get_task_status(self, task_id: str) -> Optional[MonitorTask]:
        """获取任务状态"""
        return self.storage.get_task(task_id)
    
    async def get_all_tasks(self) -> Dict[str, MonitorTask]:
        """获取所有活跃任务"""
        return self.active_tasks.copy()
    
    async def _load_active_tasks(self):
        """加载现有的活跃任务"""
        try:
            tasks = self.storage.get_all_active_tasks()
            
            for task in tasks:
                # 检查任务是否过期
                if task.expires_at < datetime.now():
                    await self._expire_task(task.task_id)
                    continue
                
                self.active_tasks[task.task_id] = task
            
            # 更新监控的符号集合
            await self._update_monitored_symbols()

            logger.info(f"加载了 {len(self.active_tasks)} 个活跃监控任务")
            self._snapshot_active_tasks()

        except Exception as e:
            logger.error(f"加载活跃任务失败: {e}")
    
    async def _update_monitored_symbols(self):
        """更新需要监控的符号集合"""
        try:
            option_symbols = {
                task.monitor_symbol
                for task in self.active_tasks.values()
                if task.monitor_instrument == "option"
            }
            spot_symbols = {
                task.monitor_symbol
                for task in self.active_tasks.values()
                if task.monitor_instrument == "spot"
            }

            if option_symbols != self.monitored_option_symbols:
                self.monitored_option_symbols = option_symbols

                if self.ws_client.ws:
                    await self.ws_client.subscribe_tickers(self.monitored_option_symbols)

                logger.info("更新期权监控符号: %s 个", len(self.monitored_option_symbols))

            if spot_symbols != self.monitored_spot_symbols:
                self.monitored_spot_symbols = spot_symbols
                await self._ensure_spot_worker()
                logger.info("更新现货监控符号: %s 个", len(self.monitored_spot_symbols))

        except Exception as e:
            logger.error(f"更新监控符号失败: {e}")

    async def _ensure_spot_worker(self):
        """确保现货价格监控任务运行状态"""
        if self.monitored_spot_symbols and not self._spot_task:
            logger.info("启动现货价格监控任务，符号: %s", ','.join(sorted(self.monitored_spot_symbols)))
            self._spot_task = asyncio.create_task(self._spot_price_worker())
        elif not self.monitored_spot_symbols and self._spot_task:
            self._spot_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._spot_task
            self._spot_task = None

    async def _spot_price_worker(self):
        """定期拉取现货价格"""
        timeout = aiohttp.ClientTimeout(total=10)
        session = aiohttp.ClientSession(timeout=timeout)
        current_task = asyncio.current_task()
        try:
            while self.running and self.monitored_spot_symbols:
                symbols = list(self.monitored_spot_symbols)
                for symbol in symbols:
                    price = await self._fetch_spot_price(session, symbol)
                    if price is not None:
                        await self._handle_spot_price(symbol, price)
                await asyncio.sleep(max(0.5, MonitorConfig.SPOT_POLL_INTERVAL))
        except asyncio.CancelledError:
            logger.info("现货价格监控任务已取消")
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("现货价格监控任务异常: %s", exc)
        finally:
            await session.close()
            if self._spot_task is current_task:
                self._spot_task = None
            if self.running and self.monitored_spot_symbols:
                logger.info("现货监控任务即将重启")
                self._spot_task = asyncio.create_task(self._spot_price_worker())

    async def _fetch_spot_price(self, session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
        """获取现货最新价格"""
        url = f"{MonitorConfig.MARKET_BASE_URL}/v5/market/tickers"
        params = {
            "category": "spot",
            "symbol": symbol,
        }
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning("获取现货价格失败 %s: HTTP %s", symbol, response.status)
                    return None
                payload = await response.json()
        except asyncio.TimeoutError:
            logger.warning("获取现货价格超时: %s", symbol)
            return None
        except aiohttp.ClientError as exc:
            logger.warning("获取现货价格网络错误 %s: %s", symbol, exc)
            return None
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("获取现货价格异常 %s: %s", symbol, exc)
            return None

        try:
            result = payload.get('result', {})
            items = result.get('list') or []
            if not items:
                return None
            record = items[0]
            price_str = record.get('lastPrice') or record.get('markPrice') or record.get('indexPrice')
            if not price_str:
                return None
            return float(price_str)
        except (ValueError, TypeError) as exc:
            logger.warning("解析现货价格失败 %s: %s", symbol, exc)
            return None

    async def _handle_spot_price(self, symbol: str, current_price: float):
        """处理现货价格更新"""
        tasks_to_check = [
            task for task in self.active_tasks.values()
            if task.monitor_instrument == "spot" and task.monitor_symbol == symbol and task.status == "active"
        ]

        for task in tasks_to_check:
            trigger_direction = await self._check_price_target(task, current_price)
            if trigger_direction:
                await self._trigger_task(task, current_price, trigger_direction)
            else:
                task.previous_price = task.current_price
                task.current_price = current_price
    
    async def _on_price_update(self, price_update: PriceUpdate):
        """处理价格更新"""
        symbol = price_update.symbol
        current_price = price_update.price
        
        # 查找需要检查的任务
        tasks_to_check = [
            task for task in self.active_tasks.values()
            if task.monitor_instrument == "option" and task.monitor_symbol == symbol and task.status == "active"
        ]
        
        for task in tasks_to_check:
            # 检查是否达到目标价格（需要在更新价格之前检查）
            trigger_direction = await self._check_price_target(task, current_price)
            if trigger_direction:
                await self._trigger_task(task, current_price, trigger_direction)
            else:
                # 更新任务的价格历史（只有未触发时才更新）
                task.previous_price = task.current_price
                task.current_price = current_price
    
    async def _check_price_target(self, task: MonitorTask, current_price: float) -> str:
        """检查是否达到目标价格（支持上穿和下穿触发）
        
        Returns:
            str: 触发方向 "up_cross", "down_cross", 或 "" (未触发)
        """
        target_price = task.target_price
        previous_price = task.previous_price
        
        # 如果没有历史价格，不触发（需要至少有一次价格更新来判断方向）
        if previous_price is None:
            return ""
        
        # 检查价格穿越目标价格
        # 上穿：之前价格小于目标价格，当前价格大于等于目标价格
        crossed_up = previous_price < target_price <= current_price
        
        # 下穿：之前价格大于目标价格，当前价格小于等于目标价格  
        crossed_down = previous_price > target_price >= current_price
        
        if crossed_up:
            logger.debug(f"价格上穿触发: {task.task_id}, {previous_price} -> {current_price}, 目标: {target_price}")
            return "up_cross"
        elif crossed_down:
            logger.debug(f"价格下穿触发: {task.task_id}, {previous_price} -> {current_price}, 目标: {target_price}")
            return "down_cross"
        
        return ""
    
    async def _trigger_task(self, task: MonitorTask, triggered_price: float, trigger_direction: str):
        """触发任务（确保只触发一次）"""
        try:
            task_id = task.task_id
            triggered_at = datetime.now()
            
            # 检查任务状态，确保只触发一次
            if task.status != "active":
                logger.warning(f"任务 {task_id} 状态非活跃，跳过触发")
                return
            
            direction_text = "上穿" if trigger_direction == "up_cross" else "下穿"
            logger.info(f"任务触发: {task_id}, 目标价格: {task.target_price}, 触发价格: {triggered_price}, 方向: {direction_text}")
            
            # 立即更新任务状态为触发中，防止重复触发
            task.status = "triggered"
            task.triggered_at = triggered_at
            
            # 更新存储中的任务状态
            self.storage.update_task_status(task_id, "triggered", triggered_at)
            
            # 从活跃任务中移除
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            
            # 发送webhook
            await self._send_webhook(task, triggered_price, trigger_direction, triggered_at)
            
            # 更新监控符号（如果没有其他任务监控同一符号）
            await self._update_monitored_symbols()
            
        except Exception as e:
            logger.error(f"触发任务失败: {e}")

        finally:
            self._snapshot_active_tasks()
    
    async def _send_webhook(self, task: MonitorTask, triggered_price: float, trigger_direction: str, triggered_at: datetime):
        """发送webhook通知"""
        try:
            webhook_data = WebhookData(
                task_id=task.task_id,
                option_symbol=task.option_info.symbol,
                monitor_symbol=task.monitor_symbol,
                monitor_instrument=task.monitor_instrument,
                target_price=task.target_price,
                triggered_price=triggered_price,
                previous_price=task.previous_price or 0.0,
                trigger_direction=trigger_direction,
                triggered_at=triggered_at.isoformat(),
                strategy_id=task.strategy_id,
                level_id=task.level_id,
                monitor_type=task.monitor_type,
                metadata=task.metadata
            )
            
            # 发送HTTP POST请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    task.webhook_url,
                    json=webhook_data.to_dict(),
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Webhook发送成功: {task.task_id} -> {task.webhook_url}")
                    else:
                        logger.warning(f"Webhook响应异常: {response.status}, 任务: {task.task_id}")
                        
        except asyncio.TimeoutError:
            logger.error(f"Webhook超时: {task.task_id} -> {task.webhook_url}")
        except Exception as e:
            logger.error(f"发送webhook失败: {e}, 任务: {task.task_id}")
    
    async def _expire_task(self, task_id: str):
        """过期任务"""
        try:
            self.storage.update_task_status(task_id, "expired")
            
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            
            logger.info(f"任务已过期: {task_id}")
            
        except Exception as e:
            logger.error(f"过期任务失败: {e}")
        finally:
            self._snapshot_active_tasks()
    
    async def _periodic_cleanup(self):
        """定期清理过期任务"""
        while self.running:
            try:
                await asyncio.sleep(300)  # 每5分钟执行一次
                
                current_time = datetime.now()
                expired_tasks = []
                
                for task_id, task in self.active_tasks.items():
                    if task.expires_at < current_time:
                        expired_tasks.append(task_id)
                
                for task_id in expired_tasks:
                    await self._expire_task(task_id)

                if expired_tasks:
                    await self._update_monitored_symbols()
                    logger.info(f"清理了 {len(expired_tasks)} 个过期任务")
                    self._snapshot_active_tasks()
            except Exception as e:
                logger.error(f"定期清理任务错误: {e}")
                self._snapshot_active_tasks()
        self._snapshot_active_tasks()

    def _snapshot_active_tasks(self) -> None:
        """写入当前活跃任务的快照文件。"""
        try:
            file_path = MonitorConfig.ACTIVE_TASKS_FILE
            file_path.parent.mkdir(parents=True, exist_ok=True)
            tasks_payload = []
            for task in self.active_tasks.values():
                tasks_payload.append({
                    "task_id": task.task_id,
                    "option_symbol": task.option_info.symbol,
                    "monitor_symbol": task.monitor_symbol,
                    "monitor_instrument": task.monitor_instrument,
                    "target_price": task.target_price,
                    "status": task.status,
                    "monitor_type": task.monitor_type,
                    "strategy_id": task.strategy_id,
                    "level_id": task.level_id,
                    "webhook_url": task.webhook_url,
                    "created_at": task.created_at.isoformat(),
                    "expires_at": task.expires_at.isoformat(),
                    "current_price": task.current_price,
                    "previous_price": task.previous_price,
                    "triggered_at": task.triggered_at.isoformat() if task.triggered_at else None,
                })

            payload = {
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "tasks": tasks_payload,
            }
            file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to persist active task snapshot: %s", exc)

# 全局服务实例
_monitor_service: Optional[PriceMonitorService] = None

async def get_monitor_service() -> PriceMonitorService:
    """获取监控服务实例"""
    global _monitor_service
    if _monitor_service is None:
        _monitor_service = PriceMonitorService()
        await _monitor_service.start()
    return _monitor_service

async def stop_monitor_service():
    """停止监控服务"""
    global _monitor_service
    if _monitor_service:
        await _monitor_service.stop()
        _monitor_service = None
