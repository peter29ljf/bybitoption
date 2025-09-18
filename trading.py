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
                   price: str = None, auto_confirm: bool = False) -> Dict:
        """买入期权"""
        print(f"正在买入期权 {symbol}...")
        print(f"数量: {quantity}")
        print(f"订单类型: {'市价单' if order_type == 'Market' else '限价单'}")
        
        if price and order_type != "Market":
            print(f"限价: {price}")
        
        # 确认订单
        if not auto_confirm:
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
                    price: str = None, auto_confirm: bool = False) -> Dict:
        """卖出期权"""
        print(f"正在卖出期权 {symbol}...")
        print(f"数量: {quantity}")
        print(f"订单类型: {'市价单' if order_type == 'Market' else '限价单'}")
        
        if price and order_type != "Market":
            print(f"限价: {price}")
        
        # 确认订单
        if not auto_confirm:
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
        """处理交易所响应，基于实际状态判断是否成交"""
        ret_code = result.get('retCode')
        ret_msg = result.get('retMsg')
        order_data = result.get('result') or {}
        order_status = order_data.get('orderStatus') or order_data.get('status')
        result_summary = self._summarize_exchange_response(ret_code, ret_msg, order_status, order_data)

        normalized_status = (order_status or "").lower()
        success = bool(
            ret_code == 0
            and normalized_status not in {"cancelled", "rejected"}
        )
        if ret_code == 0 and not order_status:
            success = True

        if success:
            print(f"\n{Fore.GREEN}✓ {action}交易所确认: {result_summary}{Style.RESET_ALL}")
        else:
            failure_reason = result_summary or ret_msg or '交易所返回不成功状态'
            print(f"\n{Fore.RED}✗ {action}执行失败: {failure_reason}{Style.RESET_ALL}")

        return {
            'success': success,
            'error': None if success else (ret_msg or '交易未成交'),
            'message': result_summary,
            'order_id': order_data.get('orderId'),
            'order_link_id': order_data.get('orderLinkId'),
            'result': order_data,
        }

    @staticmethod
    def _summarize_exchange_response(ret_code: Optional[int], ret_msg: Optional[str], order_status: Optional[str], order_data: Dict) -> str:
        """构建基于交易所返回的简洁描述"""
        parts = []
        if order_status:
            parts.append(f"状态={order_status}")
        if ret_msg:
            parts.append(f"信息={ret_msg}")
        if ret_code not in (None, 0):
            parts.append(f"retCode={ret_code}")

        if not parts:
            snapshot = {
                k: order_data.get(k)
                for k in ("orderStatus", "execStatus", "rejectReason", "retMsg")
                if order_data.get(k) is not None
            }
            if snapshot:
                parts.append(", ".join(f"{k}={v}" for k, v in snapshot.items()))
        return "，".join(parts) or "交易所未提供状态"
    
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
