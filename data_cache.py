"""
数据缓存系统
用于缓存期权链数据，避免频繁API调用
"""
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from bybit_api import BybitAPI

class DataCache:
    """数据缓存管理器"""
    
    def __init__(self, cache_dir: str = "cache"):
        """初始化缓存管理器"""
        self.cache_dir = cache_dir
        self.api_client = BybitAPI()
        
        # 确保缓存目录存在
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        # 内存缓存
        self.memory_cache = {}
        
    def get_cache_file_path(self, base_coin: str, data_type: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{base_coin}_{data_type}.json")
    
    def save_to_file(self, data: Dict, base_coin: str, data_type: str):
        """保存数据到文件"""
        cache_file = self.get_cache_file_path(base_coin, data_type)
        cache_data = {
            'timestamp': time.time(),
            'datetime': datetime.now().isoformat(),
            'data': data
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    def load_from_file(self, base_coin: str, data_type: str) -> Optional[Dict]:
        """从文件加载数据"""
        cache_file = self.get_cache_file_path(base_coin, data_type)
        
        if not os.path.exists(cache_file):
            return None
            
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # 检查数据是否过期（1小时）
            cache_time = cache_data.get('timestamp', 0)
            if time.time() - cache_time > 3600:  # 1小时过期
                return None
                
            return cache_data['data']
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return None
    
    def refresh_option_data(self, base_coin: str = 'BTC') -> Dict:
        """刷新期权数据"""
        print(f"正在刷新 {base_coin} 期权数据...")
        
        try:
            # 获取期权合约信息
            instruments_result = self.api_client.get_option_chain(base_coin)
            if instruments_result.get('retCode') != 0:
                raise Exception(f"获取期权合约失败: {instruments_result.get('retMsg')}")
            
            # 获取期权价格数据
            tickers_result = self.api_client.get_option_tickers(base_coin=base_coin)
            if tickers_result.get('retCode') != 0:
                raise Exception(f"获取期权价格失败: {tickers_result.get('retMsg')}")
            
            # 处理合约数据
            instruments = instruments_result.get('result', {}).get('list', [])
            tickers = tickers_result.get('result', {}).get('list', [])
            
            # 创建ticker字典用于快速查找
            ticker_dict = {ticker['symbol']: ticker for ticker in tickers}
            
            # 处理数据
            processed_data = []
            strike_prices = set()
            expiry_timestamps = set()
            
            for instrument in instruments:
                symbol = instrument.get('symbol', '')
                
                # 从symbol中解析执行价格
                strike_price = 0
                try:
                    parts = symbol.split('-')
                    if len(parts) >= 3:
                        strike_price = float(parts[2])
                        strike_prices.add(strike_price)
                except (ValueError, IndexError):
                    continue
                
                # 获取到期时间
                expiry_time = instrument.get('deliveryTime')
                if expiry_time:
                    expiry_timestamps.add(int(expiry_time))
                
                # 获取对应的ticker数据
                ticker = ticker_dict.get(symbol, {})
                
                option_data = {
                    'symbol': symbol,
                    'strike_price': strike_price,
                    'option_type': instrument.get('optionsType', ''),
                    'expiry_date': expiry_time,
                    'status': instrument.get('status', ''),
                    'base_coin': instrument.get('baseCoin', ''),
                    'quote_coin': instrument.get('quoteCoin', ''),
                    'bid_price': float(ticker.get('bid1Price', 0)),
                    'ask_price': float(ticker.get('ask1Price', 0)),
                    'mark_price': float(ticker.get('markPrice', 0)),
                    'last_price': float(ticker.get('lastPrice', 0)),
                    'volume_24h': float(ticker.get('volume24h', 0)),
                    'open_interest': float(ticker.get('openInterest', 0)),
                    'iv': float(ticker.get('markIv', 0)) * 100 if ticker.get('markIv') else 0,
                    'delta': float(ticker.get('delta', 0)),
                    'gamma': float(ticker.get('gamma', 0)),
                    'theta': float(ticker.get('theta', 0)),
                    'vega': float(ticker.get('vega', 0))
                }
                
                processed_data.append(option_data)
            
            # 准备缓存数据
            cache_data = {
                'options': processed_data,
                'strike_prices': sorted(list(strike_prices)),
                'expiry_timestamps': sorted(list(expiry_timestamps)),
                'total_contracts': len(processed_data),
                'refresh_time': datetime.now().isoformat()
            }
            
            # 保存到文件和内存
            self.save_to_file(cache_data, base_coin, 'options')
            self.memory_cache[f"{base_coin}_options"] = cache_data
            
            print(f"✅ {base_coin} 数据刷新完成:")
            print(f"   期权合约: {len(processed_data)} 个")
            print(f"   执行价格: {len(strike_prices)} 个")
            print(f"   到期日期: {len(expiry_timestamps)} 个")
            
            return {
                'success': True,
                'message': f'成功刷新 {base_coin} 数据',
                'stats': {
                    'total_contracts': len(processed_data),
                    'strike_prices_count': len(strike_prices),
                    'expiry_dates_count': len(expiry_timestamps),
                    'refresh_time': cache_data['refresh_time']
                }
            }
            
        except Exception as e:
            print(f"❌ 刷新 {base_coin} 数据失败: {e}")
            return {
                'success': False,
                'message': f'刷新 {base_coin} 数据失败: {str(e)}'
            }
    
    def get_cached_options(self, base_coin: str = 'BTC') -> List[Dict]:
        """获取缓存的期权数据"""
        # 先尝试内存缓存
        memory_key = f"{base_coin}_options"
        if memory_key in self.memory_cache:
            return self.memory_cache[memory_key]['options']
        
        # 再尝试文件缓存
        cached_data = self.load_from_file(base_coin, 'options')
        if cached_data:
            self.memory_cache[memory_key] = cached_data
            return cached_data['options']
        
        return []
    
    def get_cached_strike_prices(self, base_coin: str = 'BTC') -> List[float]:
        """获取缓存的执行价格"""
        memory_key = f"{base_coin}_options"
        if memory_key in self.memory_cache:
            return self.memory_cache[memory_key]['strike_prices']
        
        cached_data = self.load_from_file(base_coin, 'options')
        if cached_data:
            return cached_data['strike_prices']
        
        return []
    
    def get_cached_expiry_dates(self, base_coin: str = 'BTC') -> List[int]:
        """获取缓存的到期时间戳"""
        memory_key = f"{base_coin}_options"
        if memory_key in self.memory_cache:
            return self.memory_cache[memory_key]['expiry_timestamps']
        
        cached_data = self.load_from_file(base_coin, 'options')
        if cached_data:
            return cached_data['expiry_timestamps']
        
        return []
    
    def get_cache_status(self, base_coin: str = 'BTC') -> Dict:
        """获取缓存状态"""
        cache_file = self.get_cache_file_path(base_coin, 'options')
        
        if not os.path.exists(cache_file):
            return {
                'cached': False,
                'message': '暂无缓存数据，请点击刷新获取最新数据'
            }
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            cache_time = cache_data.get('timestamp', 0)
            cache_datetime = datetime.fromtimestamp(cache_time)
            is_expired = time.time() - cache_time > 3600
            
            stats = cache_data.get('data', {})
            
            return {
                'cached': True,
                'cache_time': cache_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'is_expired': is_expired,
                'total_contracts': stats.get('total_contracts', 0),
                'strike_prices_count': len(stats.get('strike_prices', [])),
                'expiry_dates_count': len(stats.get('expiry_timestamps', [])),
                'message': '数据已过期，建议刷新' if is_expired else '数据是最新的'
            }
            
        except Exception:
            return {
                'cached': False,
                'message': '缓存数据损坏，请重新刷新'
            }
    
    def clear_cache(self, base_coin: str = None):
        """清除缓存"""
        if base_coin:
            # 清除特定币种的缓存
            cache_file = self.get_cache_file_path(base_coin, 'options')
            if os.path.exists(cache_file):
                os.remove(cache_file)
            
            memory_key = f"{base_coin}_options"
            if memory_key in self.memory_cache:
                del self.memory_cache[memory_key]
        else:
            # 清除所有缓存
            if os.path.exists(self.cache_dir):
                for file in os.listdir(self.cache_dir):
                    if file.endswith('.json'):
                        os.remove(os.path.join(self.cache_dir, file))
            
            self.memory_cache.clear()

# 创建全局缓存实例
data_cache = DataCache()

