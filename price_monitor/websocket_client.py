"""
WebSocket客户端用于实时价格监控
"""
import json
import logging
import asyncio
import websockets
from typing import Dict, Set, Callable, Optional
from datetime import datetime
from .models import PriceUpdate
from .config import MonitorConfig

logger = logging.getLogger(__name__)

class BybitWebSocketClient:
    """Bybit WebSocket客户端"""
    
    def __init__(self):
        self.ws = None
        self.subscribed_symbols: Set[str] = set()
        self.price_callback: Optional[Callable[[PriceUpdate], None]] = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
    async def connect(self):
        """连接到WebSocket"""
        try:
            self.ws = await websockets.connect(
                MonitorConfig.WS_URL,
                ping_interval=20,
                ping_timeout=10
            )
            self.running = True
            self.reconnect_attempts = 0
            logger.info(f"WebSocket连接成功: {MonitorConfig.WS_URL}")
            
            # 启动消息处理
            asyncio.create_task(self._message_handler())
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            raise
    
    async def disconnect(self):
        """断开WebSocket连接"""
        self.running = False
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket连接已断开")
    
    async def subscribe_tickers(self, symbols: Set[str]):
        """订阅期权价格ticker数据"""
        if not self.ws:
            raise RuntimeError("WebSocket未连接")
        
        # 取消旧的订阅
        if self.subscribed_symbols:
            await self._unsubscribe_symbols(self.subscribed_symbols)

        # 订阅新的符号
        if symbols:
            await self._subscribe_symbols(symbols)
            self.subscribed_symbols = symbols.copy()
            logger.info(f"已订阅 {len(symbols)} 个期权合约的价格数据")
        else:
            self.subscribed_symbols = set()
            logger.info("已取消所有期权合约价格订阅")
    
    async def _subscribe_symbols(self, symbols: Set[str]):
        """订阅指定符号"""
        # Bybit期权WebSocket订阅格式
        subscribe_msg = {
            "op": "subscribe",
            "args": [f"tickers.{symbol}" for symbol in symbols]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        logger.debug(f"发送订阅请求: {subscribe_msg}")
    
    async def _unsubscribe_symbols(self, symbols: Set[str]):
        """取消订阅指定符号"""
        unsubscribe_msg = {
            "op": "unsubscribe",
            "args": [f"tickers.{symbol}" for symbol in symbols]
        }
        
        await self.ws.send(json.dumps(unsubscribe_msg))
        logger.debug(f"发送取消订阅请求: {unsubscribe_msg}")
    
    async def _message_handler(self):
        """处理WebSocket消息"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误: {e}, 消息: {message}")
                except Exception as e:
                    logger.error(f"处理消息错误: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket连接已关闭")
            if self.running:
                await self._reconnect()
        except Exception as e:
            logger.error(f"消息处理异常: {e}")
            if self.running:
                await self._reconnect()
    
    async def _process_message(self, data: Dict):
        """处理接收到的消息"""
        # 处理订阅确认
        if data.get('success') and data.get('op') == 'subscribe':
            logger.info(f"订阅成功: {data.get('args', [])}")
            return
        
        # 处理心跳
        if data.get('op') == 'ping':
            pong_msg = {"op": "pong"}
            await self.ws.send(json.dumps(pong_msg))
            return
        
        # 处理ticker数据
        if data.get('topic') and data.get('topic').startswith('tickers.'):
            await self._process_ticker_data(data)
    
    async def _process_ticker_data(self, data: Dict):
        """处理ticker价格数据"""
        try:
            topic = data.get('topic', '')
            symbol = topic.replace('tickers.', '')
            
            ticker_data = data.get('data', {})
            if not ticker_data:
                return
            
            # 提取价格信息（使用标记价格作为当前价格）
            mark_price = ticker_data.get('markPrice')
            if not mark_price:
                return
            
            price = float(mark_price)
            timestamp = datetime.now()
            
            # 创建价格更新对象
            price_update = PriceUpdate(
                symbol=symbol,
                price=price,
                timestamp=timestamp
            )
            
            # 调用价格回调函数
            if self.price_callback:
                try:
                    await self._call_price_callback(price_update)
                except Exception as e:
                    logger.error(f"价格回调函数执行错误: {e}")
            
            logger.debug(f"收到价格更新: {symbol} = {price}")
            
        except Exception as e:
            logger.error(f"处理ticker数据错误: {e}")
    
    async def _call_price_callback(self, price_update: PriceUpdate):
        """调用价格回调函数"""
        if asyncio.iscoroutinefunction(self.price_callback):
            await self.price_callback(price_update)
        else:
            self.price_callback(price_update)
    
    async def _reconnect(self):
        """重连逻辑"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("达到最大重连次数，停止重连")
            self.running = False
            return
        
        self.reconnect_attempts += 1
        wait_time = min(60, 2 ** self.reconnect_attempts)  # 指数退避，最大60秒
        
        logger.info(f"尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})，等待 {wait_time} 秒...")
        await asyncio.sleep(wait_time)
        
        try:
            await self.connect()
            
            # 重新订阅之前的符号
            if self.subscribed_symbols:
                await self.subscribe_tickers(self.subscribed_symbols)
                
        except Exception as e:
            logger.error(f"重连失败: {e}")
            if self.running:
                await self._reconnect()
    
    def set_price_callback(self, callback: Callable[[PriceUpdate], None]):
        """设置价格更新回调函数"""
        self.price_callback = callback

