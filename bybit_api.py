"""
Bybit API 客户端
"""
import hashlib
import hmac
import json
import time
from typing import Dict, List, Optional, Any
import requests
from config import Config


class BybitAPI:
    """Bybit API 客户端类"""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        """初始化 API 客户端"""
        self.api_key = api_key or Config.BYBIT_API_KEY
        self.api_secret = api_secret or Config.BYBIT_API_SECRET
        self.base_url = Config.BYBIT_BASE_URL
        self.timeout = Config.REQUEST_TIMEOUT
        
        if not self.api_key or not self.api_secret:
            print("警告: API 密钥未设置，将只能使用公开接口")
    
    def _generate_signature(self, params: str, timestamp: str, recv_window: str) -> str:
        """生成签名"""
        param_str = timestamp + self.api_key + recv_window + params
        return hmac.new(
            bytes(self.api_secret, "utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        """发送请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Content-Type': 'application/json'
        }
        
        # 对于需要签名的请求，添加API密钥
        if signed and self.api_key:
            headers['X-BAPI-API-KEY'] = self.api_key
        
        if signed and self.api_key and self.api_secret:
            timestamp = str(int(time.time() * 1000))
            recv_window = '5000'
            
            if method == 'GET':
                query_string = '&'.join([f"{k}={v}" for k, v in (params or {}).items()])
                param_str = query_string
            else:
                param_str = json.dumps(params) if params else ''
            
            signature = self._generate_signature(param_str, timestamp, recv_window)
            
            headers.update({
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': recv_window
            })
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            else:
                response = requests.post(url, json=params, headers=headers, timeout=self.timeout)
            
            # 如果是403错误，可能是IP白名单或API权限问题
            if response.status_code == 403:
                print(f"403错误: 可能的原因 - IP未加入白名单、API权限不足或签名错误")
                print(f"请求URL: {url}")
                
            response.raise_for_status()
            result = response.json()
            
            # 检查API返回的错误码
            if result.get('retCode') != 0:
                print(f"API错误: {result.get('retMsg', '未知错误')}")
                
            return result
        
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            return {'retCode': -1, 'retMsg': str(e)}
    
    def get_option_chain(self, base_coin: str = 'BTC', limit: int = 200) -> Dict:
        """获取期权链数据"""
        endpoint = '/v5/market/instruments-info'
        params = {
            'category': 'option',
            'baseCoin': base_coin,
            'limit': limit
        }
        
        return self._make_request('GET', endpoint, params, signed=False)
    
    def get_option_tickers(self, symbol: str = None, base_coin: str = 'BTC') -> Dict:
        """获取期权ticker数据"""
        endpoint = '/v5/market/tickers'
        params = {
            'category': 'option'
        }
        
        if symbol:
            params['symbol'] = symbol
        else:
            params['baseCoin'] = base_coin
            
        return self._make_request('GET', endpoint, params, signed=False)
    
    def get_positions(self, category: str = 'option', symbol: str = None) -> Dict:
        """获取持仓信息"""
        endpoint = '/v5/position/list'
        params = {
            'category': category
        }
        
        if symbol:
            params['symbol'] = symbol
            
        return self._make_request('GET', endpoint, params, signed=True)
    
    def get_wallet_balance(self, account_type: str = 'UNIFIED') -> Dict:
        """获取钱包余额"""
        endpoint = '/v5/account/wallet-balance'
        params = {
            'accountType': account_type
        }
        
        return self._make_request('GET', endpoint, params, signed=True)
    
    def get_option_greeks(self, base_coin: str = 'BTC') -> Dict:
        """获取期权希腊字母"""
        endpoint = '/v5/market/option-delivery-price'
        params = {
            'category': 'option',
            'baseCoin': base_coin
        }
        
        return self._make_request('GET', endpoint, params, signed=False)
    
    def get_api_key_info(self) -> Dict:
        """获取API密钥信息和权限"""
        endpoint = '/v5/user/query-api'
        return self._make_request('GET', endpoint, signed=True)
    
    def place_order(self, category: str, symbol: str, side: str, order_type: str, 
                   qty: str, price: str = None, time_in_force: str = "GTC") -> Dict:
        """下单"""
        import time
        endpoint = '/v5/order/create'
        
        # 生成唯一的订单链接ID
        order_link_id = f"option_{int(time.time() * 1000)}"
        
        params = {
            'category': category,
            'symbol': symbol,
            'side': side,
            'orderType': order_type,
            'qty': qty,
            'orderLinkId': order_link_id
        }
        
        # 只有限价单需要timeInForce和price
        if order_type != 'Market':
            params['timeInForce'] = time_in_force
            if price:
                params['price'] = price
            
        return self._make_request('POST', endpoint, params, signed=True)
    
    def get_order_history(self, category: str = 'option', symbol: str = None, limit: int = 50) -> Dict:
        """获取订单历史"""
        endpoint = '/v5/order/history'
        params = {
            'category': category,
            'limit': limit
        }
        
        if symbol:
            params['symbol'] = symbol
            
        return self._make_request('GET', endpoint, params, signed=True)
    
    def cancel_order(self, category: str, symbol: str, order_id: str = None, 
                    order_link_id: str = None) -> Dict:
        """取消订单"""
        endpoint = '/v5/order/cancel'
        params = {
            'category': category,
            'symbol': symbol
        }
        
        if order_id:
            params['orderId'] = order_id
        elif order_link_id:
            params['orderLinkId'] = order_link_id
            
        return self._make_request('POST', endpoint, params, signed=True)
