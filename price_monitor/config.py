"""
价格监控配置文件
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class MonitorConfig:
    """价格监控配置类"""
    
    # 服务配置
    HOST = os.getenv('MONITOR_HOST', '0.0.0.0')
    PORT = int(os.getenv('MONITOR_PORT', 8888))
    DEBUG = os.getenv('MONITOR_DEBUG', 'true').lower() == 'true'
    
    # Bybit WebSocket配置
    WS_URL_TESTNET = 'wss://stream-testnet.bybit.com/v5/public/option'
    WS_URL_MAINNET = 'wss://stream.bybit.com/v5/public/option'
    
    # 从父项目继承API配置
    BYBIT_TESTNET = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
    WS_URL = WS_URL_TESTNET if BYBIT_TESTNET else WS_URL_MAINNET
    
    # 监控任务配置
    MAX_TASKS = int(os.getenv('MAX_MONITOR_TASKS', 100))
    TASK_TIMEOUT = int(os.getenv('TASK_TIMEOUT_HOURS', 24)) * 3600  # 24小时
    
    # 数据存储配置
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    USE_REDIS = os.getenv('USE_REDIS', 'false').lower() == 'true'
    
    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'price_monitor.log')

    # 活跃任务快照文件
    ACTIVE_TASKS_FILE = Path(__file__).resolve().parent / "active_tasks.json"

