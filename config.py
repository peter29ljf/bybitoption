"""
配置文件
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """配置类"""
    
    # Bybit API 配置
    BYBIT_API_KEY = os.getenv('BYBIT_API_KEY', '')
    BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET', '')
    BYBIT_TESTNET = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
    
    # API 基础URL
    BYBIT_BASE_URL = 'https://api-testnet.bybit.com' if BYBIT_TESTNET else 'https://api.bybit.com'
    
    # 默认请求超时时间（秒）
    REQUEST_TIMEOUT = 10
    
    # 支持的期权类型
    OPTION_TYPES = ['Call', 'Put']
    
    # 默认期权合约设置
    DEFAULT_CATEGORY = 'option'
    DEFAULT_BASE_COIN = 'BTC'  # 支持 BTC, ETH
