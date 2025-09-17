"""
持仓查询模块
"""
from typing import List, Dict, Optional
from tabulate import tabulate
from colorama import Fore, Style, init
from bybit_api import BybitAPI

# 初始化colorama
init()


class PositionManager:
    """持仓管理类"""
    
    def __init__(self, api_client: BybitAPI):
        """初始化持仓管理"""
        self.api = api_client
    
    def get_option_positions(self, symbol: str = None) -> List[Dict]:
        """获取期权持仓"""
        print("正在获取期权持仓数据...")
        
        positions_data = self.api.get_positions('option', symbol)
        
        if positions_data.get('retCode') != 0:
            print(f"获取持仓失败: {positions_data.get('retMsg')}")
            return []
        
        positions = positions_data.get('result', {}).get('list', [])
        
        # 过滤出有持仓的合约
        active_positions = []
        for pos in positions:
            size = float(pos.get('size', 0))
            if size != 0:  # 只显示有持仓的合约
                active_positions.append({
                    'symbol': pos.get('symbol', ''),
                    'side': pos.get('side', ''),
                    'size': size,
                    'avg_price': float(pos.get('avgPrice', 0)),
                    'mark_price': float(pos.get('markPrice', 0)),
                    'unrealized_pnl': float(pos.get('unrealisedPnl', 0)),
                    'percentage': float(pos.get('unrealisedPnlPercentage', 0)) * 100,
                    'leverage': pos.get('leverage', '1'),
                    'risk_limit': float(pos.get('riskLimitValue') or 0),
                    'created_time': pos.get('createdTime', ''),
                    'updated_time': pos.get('updatedTime', '')
                })
        
        return active_positions
    
    def display_positions(self, positions: List[Dict]):
        """显示持仓信息"""
        if not positions:
            print(f"{Fore.YELLOW}当前没有期权持仓{Style.RESET_ALL}")
            return
        
        # 准备表格数据
        table_data = []
        total_pnl = 0
        
        for pos in positions:
            # 根据盈亏设置颜色
            pnl = pos['unrealized_pnl']
            total_pnl += pnl
            
            if pnl > 0:
                pnl_color = Fore.GREEN
            elif pnl < 0:
                pnl_color = Fore.RED
            else:
                pnl_color = Style.RESET_ALL
            
            # 格式化数据
            row = [
                pos['symbol'],
                pos['side'],
                f"{pos['size']:.4f}",
                f"{pos['avg_price']:.4f}",
                f"{pos['mark_price']:.4f}",
                f"{pnl_color}{pnl:.4f}{Style.RESET_ALL}",
                f"{pnl_color}{pos['percentage']:.2f}%{Style.RESET_ALL}",
                pos['leverage']
            ]
            table_data.append(row)
        
        # 显示表格
        headers = ['合约', '方向', '数量', '均价', '标记价', '未实现盈亏', '收益率', '杠杆']
        print(f"\n{Fore.CYAN}=== 期权持仓 ==={Style.RESET_ALL}")
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        # 显示总盈亏
        total_color = Fore.GREEN if total_pnl >= 0 else Fore.RED
        print(f"\n总未实现盈亏: {total_color}{total_pnl:.4f}{Style.RESET_ALL}")
    
    def get_wallet_info(self) -> Dict:
        """获取钱包信息"""
        print("正在获取钱包余额...")
        
        wallet_data = self.api.get_wallet_balance()
        
        if wallet_data.get('retCode') != 0:
            print(f"获取钱包余额失败: {wallet_data.get('retMsg')}")
            return {}
        
        wallet_list = wallet_data.get('result', {}).get('list', [])
        
        if not wallet_list:
            return {}
        
        # 获取统一账户信息
        unified_account = wallet_list[0]
        coins = unified_account.get('coin', [])
        
        wallet_info = {
            'account_type': unified_account.get('accountType', ''),
            'total_equity': float(unified_account.get('totalEquity') or 0),
            'total_wallet_balance': float(unified_account.get('totalWalletBalance') or 0),
            'total_margin_balance': float(unified_account.get('totalMarginBalance') or 0),
            'total_available_balance': float(unified_account.get('totalAvailableBalance') or 0),
            'total_perp_upl': float(unified_account.get('totalPerpUPL') or 0),
            'total_initial_margin': float(unified_account.get('totalInitialMargin') or 0),
            'total_maintenance_margin': float(unified_account.get('totalMaintenanceMargin') or 0),
            'coins': []
        }
        
        # 处理各个币种的余额
        for coin in coins:
            coin_balance = float(coin.get('walletBalance', 0))
            if coin_balance > 0:  # 只显示有余额的币种
                wallet_info['coins'].append({
                    'coin': coin.get('coin', ''),
                    'wallet_balance': coin_balance,
                    'available_balance': float(coin.get('availableToWithdraw') or 0),
                    'usd_value': float(coin.get('usdValue') or 0),
                    'unrealized_pnl': float(coin.get('unrealisedPnl') or 0)
                })
        
        return wallet_info
    
    def display_wallet(self, wallet_info: Dict):
        """显示钱包信息"""
        if not wallet_info:
            print(f"{Fore.YELLOW}无法获取钱包信息{Style.RESET_ALL}")
            return
        
        print(f"\n{Fore.CYAN}=== 钱包信息 ==={Style.RESET_ALL}")
        print(f"账户类型: {wallet_info['account_type']}")
        print(f"总权益: {wallet_info['total_equity']:.4f} USD")
        print(f"钱包余额: {wallet_info['total_wallet_balance']:.4f} USD")
        print(f"可用余额: {wallet_info['total_available_balance']:.4f} USD")
        print(f"保证金余额: {wallet_info['total_margin_balance']:.4f} USD")
        print(f"初始保证金: {wallet_info['total_initial_margin']:.4f} USD")
        print(f"维持保证金: {wallet_info['total_maintenance_margin']:.4f} USD")
        
        # 显示总未实现盈亏
        total_upl = wallet_info['total_perp_upl']
        upl_color = Fore.GREEN if total_upl >= 0 else Fore.RED
        print(f"总未实现盈亏: {upl_color}{total_upl:.4f} USD{Style.RESET_ALL}")
        
        # 显示各币种余额
        if wallet_info['coins']:
            print(f"\n{Fore.CYAN}=== 币种余额 ==={Style.RESET_ALL}")
            coin_table = []
            
            for coin_info in wallet_info['coins']:
                upl = coin_info['unrealized_pnl']
                upl_color = Fore.GREEN if upl >= 0 else Fore.RED
                
                row = [
                    coin_info['coin'],
                    f"{coin_info['wallet_balance']:.8f}",
                    f"{coin_info['available_balance']:.8f}",
                    f"{coin_info['usd_value']:.4f}",
                    f"{upl_color}{upl:.4f}{Style.RESET_ALL}"
                ]
                coin_table.append(row)
            
            headers = ['币种', '余额', '可用余额', 'USD价值', '未实现盈亏']
            print(tabulate(coin_table, headers=headers, tablefmt='grid'))
    
    def get_position_summary(self) -> Dict:
        """获取持仓摘要"""
        positions = self.get_option_positions()
        
        if not positions:
            return {'total_positions': 0, 'total_pnl': 0, 'long_positions': 0, 'short_positions': 0}
        
        total_pnl = sum(pos['unrealized_pnl'] for pos in positions)
        long_positions = len([pos for pos in positions if pos['side'] == 'Buy'])
        short_positions = len([pos for pos in positions if pos['side'] == 'Sell'])
        
        return {
            'total_positions': len(positions),
            'total_pnl': total_pnl,
            'long_positions': long_positions,
            'short_positions': short_positions,
            'positions': positions
        }
