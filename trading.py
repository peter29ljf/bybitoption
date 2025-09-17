"""
期权交易模块
"""
import time
from typing import Dict, Optional
from colorama import Fore, Style, init
from bybit_api import BybitAPI

# 初始化colorama
init()


class OptionTrader:
    """期权交易类"""
    
    def __init__(self, api_client: BybitAPI):
        """初始化期权交易"""
        self.api = api_client
    
    def buy_option(self, symbol: str, quantity: str, order_type: str = "Market", 
                   price: str = None) -> Dict:
        """买入期权"""
        print(f"正在买入期权 {symbol}...")
        print(f"数量: {quantity}")
        print(f"订单类型: {'市价单' if order_type == 'Market' else '限价单'}")
        
        if price and order_type != "Market":
            print(f"限价: {price}")
        
        # 确认订单
        confirm = input(f"\n{Fore.YELLOW}确认下单? (y/N): {Style.RESET_ALL}")
        if confirm.lower() != 'y':
            print("订单已取消")
            return {'cancelled': True}
        
        # 下单
        result = self.api.place_order(
            category='option',
            symbol=symbol,
            side='Buy',
            order_type=order_type,
            qty=quantity,
            price=price
        )
        
        return self._handle_order_result(result, "买入")
    
    def sell_option(self, symbol: str, quantity: str, order_type: str = "Market", 
                    price: str = None) -> Dict:
        """卖出期权"""
        print(f"正在卖出期权 {symbol}...")
        print(f"数量: {quantity}")
        print(f"订单类型: {'市价单' if order_type == 'Market' else '限价单'}")
        
        if price and order_type != "Market":
            print(f"限价: {price}")
        
        # 确认订单
        confirm = input(f"\n{Fore.YELLOW}确认下单? (y/N): {Style.RESET_ALL}")
        if confirm.lower() != 'y':
            print("订单已取消")
            return {'cancelled': True}
        
        # 下单
        result = self.api.place_order(
            category='option',
            symbol=symbol,
            side='Sell',
            order_type=order_type,
            qty=quantity,
            price=price
        )
        
        return self._handle_order_result(result, "卖出")
    
    def _handle_order_result(self, result: Dict, action: str) -> Dict:
        """处理订单结果"""
        if result.get('retCode') == 0:
            order_data = result.get('result', {})
            order_id = order_data.get('orderId', '')
            order_link_id = order_data.get('orderLinkId', '')
            
            print(f"\n{Fore.GREEN}✓ {action}订单提交成功!{Style.RESET_ALL}")
            print(f"订单ID: {order_id}")
            print(f"订单链接ID: {order_link_id}")
            
            return {
                'success': True,
                'order_id': order_id,
                'order_link_id': order_link_id,
                'result': order_data
            }
        else:
            error_msg = result.get('retMsg', '未知错误')
            print(f"\n{Fore.RED}✗ {action}订单失败: {error_msg}{Style.RESET_ALL}")
            
            return {
                'success': False,
                'error': error_msg,
                'result': result
            }
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """获取当前期权价格"""
        tickers_data = self.api.get_option_tickers(symbol=symbol)
        
        if tickers_data.get('retCode') == 0:
            tickers = tickers_data.get('result', {}).get('list', [])
            if tickers:
                ticker = tickers[0]
                mark_price = float(ticker.get('markPrice', 0))
                bid_price = float(ticker.get('bid1Price', 0))
                ask_price = float(ticker.get('ask1Price', 0))
                
                print(f"\n{Fore.CYAN}当前价格信息:{Style.RESET_ALL}")
                print(f"标记价格: {mark_price}")
                print(f"买一价: {bid_price}")
                print(f"卖一价: {ask_price}")
                
                return {
                    'mark_price': mark_price,
                    'bid_price': bid_price,
                    'ask_price': ask_price
                }
        
        print(f"{Fore.RED}无法获取价格信息{Style.RESET_ALL}")
        return None
    
    def show_order_preview(self, symbol: str, side: str, quantity: str, 
                          order_type: str = "Market", price: str = None):
        """显示订单预览"""
        print(f"\n{Fore.CYAN}=== 订单预览 ==={Style.RESET_ALL}")
        print(f"合约: {symbol}")
        print(f"方向: {'买入' if side == 'Buy' else '卖出'}")
        print(f"数量: {quantity}")
        print(f"订单类型: {'市价单' if order_type == 'Market' else '限价单'}")
        
        if price and order_type != "Market":
            print(f"限价: {price}")
        
        # 获取当前价格
        price_info = self.get_current_price(symbol)
        
        if price_info and order_type == "Market":
            estimated_price = price_info['ask_price'] if side == 'Buy' else price_info['bid_price']
            estimated_cost = estimated_price * float(quantity)
            print(f"\n预估成交价: {estimated_price}")
            print(f"预估成本: {estimated_cost:.2f} USD")
    
    def get_order_status(self, order_id: str = None, order_link_id: str = None) -> Dict:
        """查询订单状态"""
        # 这里可以添加查询订单状态的逻辑
        # Bybit API中可能需要使用不同的endpoint
        pass
    
    def cancel_order_by_id(self, symbol: str, order_id: str = None, 
                          order_link_id: str = None) -> Dict:
        """根据ID取消订单"""
        print(f"正在取消订单...")
        
        result = self.api.cancel_order(
            category='option',
            symbol=symbol,
            order_id=order_id,
            order_link_id=order_link_id
        )
        
        if result.get('retCode') == 0:
            print(f"{Fore.GREEN}✓ 订单取消成功{Style.RESET_ALL}")
            return {'success': True}
        else:
            error_msg = result.get('retMsg', '未知错误')
            print(f"{Fore.RED}✗ 订单取消失败: {error_msg}{Style.RESET_ALL}")
            return {'success': False, 'error': error_msg}
