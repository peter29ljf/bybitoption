"""
期权链查询模块
"""
from datetime import datetime
from typing import List, Dict, Optional
from tabulate import tabulate
from colorama import Fore, Style, init
from bybit_api import BybitAPI

# 初始化colorama
init()


class OptionChain:
    """期权链查询类"""
    
    def __init__(self, api_client: BybitAPI):
        """初始化期权链查询"""
        self.api = api_client
    
    def get_chain_data(self, base_coin: str = 'BTC', expiry_date: str = None) -> List[Dict]:
        """获取期权链数据"""
        print(f"正在获取 {base_coin} 期权链数据...")
        
        # 获取期权合约信息
        instruments_data = self.api.get_option_chain(base_coin)
        
        if instruments_data.get('retCode') != 0:
            print(f"获取期权合约失败: {instruments_data.get('retMsg')}")
            return []
        
        # 获取期权价格数据
        tickers_data = self.api.get_option_tickers(base_coin=base_coin)
        
        if tickers_data.get('retCode') != 0:
            print(f"获取期权价格失败: {tickers_data.get('retMsg')}")
            return []
        
        # 合并数据
        instruments = instruments_data.get('result', {}).get('list', [])
        tickers = tickers_data.get('result', {}).get('list', [])
        
        # 创建ticker字典用于快速查找
        ticker_dict = {ticker['symbol']: ticker for ticker in tickers}
        
        chain_data = []
        for instrument in instruments:
            symbol = instrument.get('symbol', '')
            
            # 如果指定了到期日，过滤合约
            if expiry_date and instrument.get('deliveryTime') != expiry_date:
                continue
            
            ticker = ticker_dict.get(symbol, {})
            
            # 从symbol中解析执行价格
            strike_price = 0
            try:
                parts = symbol.split('-')
                if len(parts) >= 3:
                    strike_price = float(parts[2])
            except (ValueError, IndexError):
                strike_price = 0
            
            chain_data.append({
                'symbol': symbol,
                'strike_price': strike_price,
                'option_type': instrument.get('optionsType', ''),
                'expiry_date': instrument.get('deliveryTime', ''),
                'bid_price': float(ticker.get('bid1Price', 0)),
                'ask_price': float(ticker.get('ask1Price', 0)),
                'mark_price': float(ticker.get('markPrice', 0)),
                'last_price': float(ticker.get('lastPrice', 0)),
                'volume_24h': float(ticker.get('volume24h', 0)),
                'open_interest': float(ticker.get('openInterest', 0)),
                'iv': float(ticker.get('markIv', 0)) * 100 if ticker.get('markIv') else 0,  # 转换为百分比
                'delta': float(ticker.get('delta', 0)),
                'gamma': float(ticker.get('gamma', 0)),
                'theta': float(ticker.get('theta', 0)),
                'vega': float(ticker.get('vega', 0))
            })
        
        return chain_data
    
    def display_chain(self, chain_data: List[Dict], strike_range: tuple = None):
        """显示期权链数据"""
        if not chain_data:
            print("没有找到期权数据")
            return
        
        # 按到期日和执行价格排序
        chain_data.sort(key=lambda x: (x['expiry_date'], x['strike_price']))
        
        # 如果指定了执行价格范围，过滤数据
        if strike_range:
            min_strike, max_strike = strike_range
            chain_data = [
                option for option in chain_data 
                if min_strike <= option['strike_price'] <= max_strike
            ]
        
        # 按到期日分组显示
        current_expiry = None
        for option in chain_data:
            if option['expiry_date'] != current_expiry:
                current_expiry = option['expiry_date']
                expiry_dt = datetime.fromtimestamp(int(current_expiry) / 1000)
                print(f"\n{Fore.CYAN}=== 到期日: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S')} ==={Style.RESET_ALL}")
                
                # 创建表格数据
                calls = []
                puts = []
                
                # 分离看涨和看跌期权
                for opt in chain_data:
                    if opt['expiry_date'] == current_expiry:
                        row = [
                            opt['strike_price'],
                            f"{opt['bid_price']:.4f}",
                            f"{opt['ask_price']:.4f}",
                            f"{opt['mark_price']:.4f}",
                            f"{opt['volume_24h']:.0f}",
                            f"{opt['open_interest']:.0f}",
                            f"{opt['iv']:.1f}%",
                            f"{opt['delta']:.3f}",
                            f"{opt['gamma']:.4f}",
                            f"{opt['theta']:.4f}",
                            f"{opt['vega']:.4f}"
                        ]
                        
                        if opt['option_type'] == 'Call':
                            calls.append(row)
                        else:
                            puts.append(row)
                
                # 显示看涨期权
                if calls:
                    print(f"\n{Fore.GREEN}看涨期权 (Call){Style.RESET_ALL}")
                    headers = ['执行价', '买价', '卖价', '标记价', '24h成交量', '持仓量', 'IV', 'Delta', 'Gamma', 'Theta', 'Vega']
                    print(tabulate(calls, headers=headers, tablefmt='grid', floatfmt='.4f'))
                
                # 显示看跌期权
                if puts:
                    print(f"\n{Fore.RED}看跌期权 (Put){Style.RESET_ALL}")
                    headers = ['执行价', '买价', '卖价', '标记价', '24h成交量', '持仓量', 'IV', 'Delta', 'Gamma', 'Theta', 'Vega']
                    print(tabulate(puts, headers=headers, tablefmt='grid', floatfmt='.4f'))
    
    def get_atm_options(self, base_coin: str = 'BTC', spot_price: float = None) -> List[Dict]:
        """获取平值期权"""
        chain_data = self.get_chain_data(base_coin)
        
        if not chain_data:
            return []
        
        # 如果没有提供现货价格，尝试从期权数据推断
        if spot_price is None:
            # 使用delta最接近0.5的看涨期权的执行价作为参考
            call_options = [opt for opt in chain_data if opt['option_type'] == 'Call']
            if call_options:
                atm_call = min(call_options, key=lambda x: abs(x['delta'] - 0.5))
                spot_price = atm_call['strike_price']
            else:
                print("无法确定现货价格")
                return []
        
        # 找到最接近现货价格的执行价
        strikes = list(set(opt['strike_price'] for opt in chain_data))
        closest_strike = min(strikes, key=lambda x: abs(x - spot_price))
        
        # 返回该执行价的所有期权
        atm_options = [
            opt for opt in chain_data 
            if opt['strike_price'] == closest_strike
        ]
        
        return atm_options
    
    def get_expiry_dates(self, base_coin: str = 'BTC') -> List[str]:
        """获取所有可用的到期日"""
        instruments_data = self.api.get_option_chain(base_coin)
        
        if instruments_data.get('retCode') != 0:
            return []
        
        instruments = instruments_data.get('result', {}).get('list', [])
        expiry_dates = list(set(
            datetime.fromtimestamp(int(inst['deliveryTime']) / 1000).strftime('%Y-%m-%d')
            for inst in instruments
            if inst.get('deliveryTime')
        ))
        
        return sorted(expiry_dates)
