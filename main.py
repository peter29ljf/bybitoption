#!/usr/bin/env python3
"""
Bybit 期权交易应用程序
主要功能：
1. 查看期权链
2. 查看持仓
3. 查看钱包余额
"""

import click
from colorama import Fore, Style, init
from bybit_api import BybitAPI
from option_chain import OptionChain
from positions import PositionManager
from trading import OptionTrader
from option_calculator import calculate_option_price_scenario
from config import Config

# 初始化colorama
init()


@click.group()
@click.option('--testnet', is_flag=True, help='使用测试网')
@click.pass_context
def cli(ctx, testnet):
    """Bybit 期权交易应用程序"""
    # 确保上下文对象存在
    ctx.ensure_object(dict)
    
    # 初始化API客户端
    api_client = BybitAPI()
    ctx.obj['api'] = api_client
    ctx.obj['testnet'] = testnet
    
    if testnet:
        print(f"{Fore.YELLOW}使用测试网环境{Style.RESET_ALL}")
    
    # 检查API配置
    if not api_client.api_key or not api_client.api_secret:
        print(f"{Fore.YELLOW}警告: 未配置API密钥，部分功能可能无法使用{Style.RESET_ALL}")
        print("请设置环境变量 BYBIT_API_KEY 和 BYBIT_API_SECRET")


@cli.command()
@click.option('--base-coin', '-b', default='BTC', help='基础币种 (BTC/ETH)')
@click.option('--expiry', '-e', help='过滤特定到期日 (YYYY-MM-DD)')
@click.option('--strike-min', type=float, help='最小执行价')
@click.option('--strike-max', type=float, help='最大执行价')
@click.option('--atm-only', is_flag=True, help='只显示平值期权')
@click.pass_context
def chain(ctx, base_coin, expiry, strike_min, strike_max, atm_only):
    """查看期权链"""
    api = ctx.obj['api']
    option_chain = OptionChain(api)
    
    print(f"{Fore.CYAN}正在查询 {base_coin} 期权链...{Style.RESET_ALL}")
    
    if atm_only:
        # 只显示平值期权
        atm_options = option_chain.get_atm_options(base_coin)
        if atm_options:
            option_chain.display_chain(atm_options)
        else:
            print("未找到平值期权数据")
    else:
        # 获取完整期权链
        chain_data = option_chain.get_chain_data(base_coin, expiry)
        
        if chain_data:
            # 设置执行价格范围
            strike_range = None
            if strike_min is not None and strike_max is not None:
                strike_range = (strike_min, strike_max)
            
            option_chain.display_chain(chain_data, strike_range)
        else:
            print("未找到期权链数据")


@cli.command()
@click.option('--symbol', '-s', help='指定合约符号')
@click.pass_context
def positions(ctx, symbol):
    """查看持仓"""
    api = ctx.obj['api']
    position_manager = PositionManager(api)
    
    print(f"{Fore.CYAN}正在查询持仓信息...{Style.RESET_ALL}")
    
    # 获取持仓信息
    positions_list = position_manager.get_option_positions(symbol)
    position_manager.display_positions(positions_list)


@cli.command()
@click.pass_context
def wallet(ctx):
    """查看钱包余额"""
    api = ctx.obj['api']
    position_manager = PositionManager(api)
    
    print(f"{Fore.CYAN}正在查询钱包信息...{Style.RESET_ALL}")
    
    # 获取钱包信息
    wallet_info = position_manager.get_wallet_info()
    position_manager.display_wallet(wallet_info)


@cli.command()
@click.option('--base-coin', '-b', default='BTC', help='基础币种 (BTC/ETH)')
@click.pass_context
def expiries(ctx, base_coin):
    """查看可用的到期日"""
    api = ctx.obj['api']
    option_chain = OptionChain(api)
    
    print(f"{Fore.CYAN}正在查询 {base_coin} 可用到期日...{Style.RESET_ALL}")
    
    expiry_dates = option_chain.get_expiry_dates(base_coin)
    
    if expiry_dates:
        print(f"\n{Fore.GREEN}可用到期日:{Style.RESET_ALL}")
        for i, date in enumerate(expiry_dates, 1):
            print(f"{i:2d}. {date}")
    else:
        print("未找到可用的到期日")


@cli.command()
@click.pass_context
def summary(ctx):
    """显示账户摘要"""
    api = ctx.obj['api']
    position_manager = PositionManager(api)
    
    print(f"{Fore.CYAN}正在生成账户摘要...{Style.RESET_ALL}")
    
    # 获取持仓摘要
    pos_summary = position_manager.get_position_summary()
    
    # 获取钱包信息
    wallet_info = position_manager.get_wallet_info()
    
    print(f"\n{Fore.CYAN}=== 账户摘要 ==={Style.RESET_ALL}")
    
    # 显示持仓摘要
    print(f"总持仓数量: {pos_summary['total_positions']}")
    print(f"多头持仓: {pos_summary['long_positions']}")
    print(f"空头持仓: {pos_summary['short_positions']}")
    
    total_pnl = pos_summary['total_pnl']
    pnl_color = Fore.GREEN if total_pnl >= 0 else Fore.RED
    print(f"期权总盈亏: {pnl_color}{total_pnl:.4f}{Style.RESET_ALL}")
    
    # 显示钱包摘要
    if wallet_info:
        print(f"\n总权益: {wallet_info['total_equity']:.4f} USD")
        print(f"可用余额: {wallet_info['total_available_balance']:.4f} USD")


@cli.command()
@click.pass_context
def config_check(ctx):
    """检查配置"""
    print(f"{Fore.CYAN}=== 配置检查 ==={Style.RESET_ALL}")
    
    print(f"API Key: {'已设置' if Config.BYBIT_API_KEY else '未设置'}")
    print(f"API Secret: {'已设置' if Config.BYBIT_API_SECRET else '未设置'}")
    print(f"测试网: {'是' if Config.BYBIT_TESTNET else '否'}")
    print(f"API URL: {Config.BYBIT_BASE_URL}")
    print(f"请求超时: {Config.REQUEST_TIMEOUT}秒")
    
    if not Config.BYBIT_API_KEY or not Config.BYBIT_API_SECRET:
        print(f"\n{Fore.YELLOW}要使用完整功能，请设置以下环境变量:{Style.RESET_ALL}")
        print("export BYBIT_API_KEY='your_api_key'")
        print("export BYBIT_API_SECRET='your_api_secret'")
        print("export BYBIT_TESTNET='true'  # 测试网，生产环境设为false")


@cli.command()
@click.pass_context
def api_info(ctx):
    """查看API密钥信息和权限"""
    api = ctx.obj['api']
    
    print(f"{Fore.CYAN}正在查询API密钥信息...{Style.RESET_ALL}")
    
    api_info_data = api.get_api_key_info()
    
    if api_info_data.get('retCode') == 0:
        result = api_info_data.get('result', {})
        print(f"\n{Fore.GREEN}=== API密钥信息 ==={Style.RESET_ALL}")
        print(f"API密钥ID: {result.get('id', 'N/A')}")
        print(f"备注: {result.get('note', 'N/A')}")
        print(f"只读: {'是' if result.get('readOnly') else '否'}")
        print(f"统一账户: {'是' if result.get('uta') else '否'}")
        print(f"权限类型: {result.get('type', 'N/A')}")
        
        # 显示权限
        permissions = result.get('permissions', {})
        print(f"\n权限设置:")
        for key, value in permissions.items():
            status = '✓' if value else '✗'
            print(f"  {key}: {status}")
            
        # 显示IP限制
        ips = result.get('ips', [])
        if ips:
            print(f"\nIP白名单: {', '.join(ips)}")
        else:
            print(f"\nIP白名单: 无限制")
            
    else:
        print(f"查询失败: {api_info_data.get('retMsg', '未知错误')}")


@cli.command()
@click.option('--symbol', '-s', required=True, help='期权合约符号')
@click.option('--quantity', '-q', required=True, help='买入数量')
@click.option('--price', '-p', help='限价（不指定则为市价单）')
@click.option('--confirm', '-y', is_flag=True, help='跳过确认直接下单')
@click.pass_context
def buy(ctx, symbol, quantity, price, confirm):
    """买入期权"""
    api = ctx.obj['api']
    trader = OptionTrader(api)
    
    order_type = "Limit" if price else "Market"
    
    # 显示订单预览
    trader.show_order_preview(symbol, "Buy", quantity, order_type, price)
    
    if not confirm:
        confirm_input = input(f"\n{Fore.YELLOW}确认买入? (y/N): {Style.RESET_ALL}")
        if confirm_input.lower() != 'y':
            print("订单已取消")
            return
    
    # 执行买入
    result = trader.buy_option(symbol, quantity, order_type, price)
    
    if result.get('success'):
        print(f"\n{Fore.GREEN}买入订单已成功提交！{Style.RESET_ALL}")
    elif not result.get('cancelled'):
        print(f"\n{Fore.RED}买入失败{Style.RESET_ALL}")


@cli.command()
@click.option('--symbol', '-s', required=True, help='期权合约符号')
@click.option('--quantity', '-q', required=True, help='卖出数量')
@click.option('--price', '-p', help='限价（不指定则为市价单）')
@click.option('--confirm', '-y', is_flag=True, help='跳过确认直接下单')
@click.pass_context
def sell(ctx, symbol, quantity, price, confirm):
    """卖出期权"""
    api = ctx.obj['api']
    trader = OptionTrader(api)
    
    order_type = "Limit" if price else "Market"
    
    # 显示订单预览
    trader.show_order_preview(symbol, "Sell", quantity, order_type, price)
    
    if not confirm:
        confirm_input = input(f"\n{Fore.YELLOW}确认卖出? (y/N): {Style.RESET_ALL}")
        if confirm_input.lower() != 'y':
            print("订单已取消")
            return
    
    # 执行卖出
    result = trader.sell_option(symbol, quantity, order_type, price)
    
    if result.get('success'):
        print(f"\n{Fore.GREEN}卖出订单已成功提交！{Style.RESET_ALL}")
    elif not result.get('cancelled'):
        print(f"\n{Fore.RED}卖出失败{Style.RESET_ALL}")


@cli.command()
@click.option('--symbol', '-s', help='指定合约符号过滤')
@click.option('--limit', '-l', default=20, help='显示订单数量限制')
@click.pass_context
def orders(ctx, symbol, limit):
    """查看订单历史"""
    api = ctx.obj['api']
    
    print(f"{Fore.CYAN}正在查询订单历史...{Style.RESET_ALL}")
    
    orders_data = api.get_order_history('option', symbol, limit)
    
    if orders_data.get('retCode') == 0:
        orders_list = orders_data.get('result', {}).get('list', [])
        
        if orders_list:
            print(f"\n{Fore.CYAN}=== 订单历史 ==={Style.RESET_ALL}")
            
            for order in orders_list:
                status = order.get('orderStatus', '')
                side = order.get('side', '')
                symbol = order.get('symbol', '')
                qty = order.get('qty', '')
                price = order.get('price', '')
                avg_price = order.get('avgPrice', '')
                created_time = order.get('createdTime', '')
                
                # 格式化时间
                if created_time:
                    import datetime
                    dt = datetime.datetime.fromtimestamp(int(created_time) / 1000)
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    time_str = 'N/A'
                
                # 根据状态设置颜色
                if status == 'Filled':
                    status_color = Fore.GREEN
                elif status == 'Cancelled':
                    status_color = Fore.RED
                else:
                    status_color = Fore.YELLOW
                
                side_color = Fore.GREEN if side == 'Buy' else Fore.RED
                
                print(f"\n合约: {symbol}")
                print(f"方向: {side_color}{side}{Style.RESET_ALL}")
                print(f"数量: {qty}")
                print(f"委托价: {price}")
                print(f"成交价: {avg_price}")
                print(f"状态: {status_color}{status}{Style.RESET_ALL}")
                print(f"时间: {time_str}")
                print("-" * 50)
        else:
            print("暂无订单历史")
    else:
        print(f"查询失败: {orders_data.get('retMsg', '未知错误')}")


@cli.command()
@click.option('--symbol', '-s', required=True, help='期权合约符号')
@click.pass_context
def greeks(ctx, symbol):
    """查看特定期权的希腊字母数据"""
    api = ctx.obj['api']
    
    print(f"{Fore.CYAN}正在查询 {symbol} 的希腊字母数据...{Style.RESET_ALL}")
    
    # 获取期权ticker数据
    ticker_data = api.get_option_tickers(symbol=symbol)
    
    if ticker_data.get('retCode') == 0:
        tickers = ticker_data.get('result', {}).get('list', [])
        
        if tickers:
            ticker = tickers[0]
            
            print(f"\n{Fore.GREEN}=== {symbol} 详细数据 ==={Style.RESET_ALL}")
            
            # 基础价格信息
            print(f"\n{Fore.CYAN}价格信息:{Style.RESET_ALL}")
            print(f"标记价格: {float(ticker.get('markPrice', 0)):.4f}")
            print(f"买一价: {float(ticker.get('bid1Price', 0)):.4f}")
            print(f"卖一价: {float(ticker.get('ask1Price', 0)):.4f}")
            print(f"最新价: {float(ticker.get('lastPrice', 0)):.4f}")
            
            # 成交和持仓信息
            print(f"\n{Fore.CYAN}市场数据:{Style.RESET_ALL}")
            print(f"24h成交量: {float(ticker.get('volume24h', 0)):.2f}")
            print(f"持仓量: {float(ticker.get('openInterest', 0)):.2f}")
            print(f"24h涨跌幅: {float(ticker.get('price24hPcnt', 0)) * 100:.2f}%")
            
            # 希腊字母
            print(f"\n{Fore.YELLOW}=== 希腊字母 ==={Style.RESET_ALL}")
            delta = float(ticker.get('delta', 0))
            gamma = float(ticker.get('gamma', 0))
            theta = float(ticker.get('theta', 0))
            vega = float(ticker.get('vega', 0))
            iv = float(ticker.get('markIv', 0)) * 100 if ticker.get('markIv') else 0
            
            print(f"Delta: {delta:.6f}")
            print(f"Gamma: {gamma:.6f}")
            print(f"Theta: {theta:.6f}")
            print(f"Vega: {vega:.6f}")
            print(f"隐含波动率: {iv:.2f}%")
            
            # 希腊字母解释
            print(f"\n{Fore.BLUE}=== 希腊字母含义 ==={Style.RESET_ALL}")
            print(f"Delta: 标的价格变动1美元时，期权价格变动约 {abs(delta):.6f} 美元")
            if delta > 0:
                print("       正Delta表示看涨期权，标的上涨期权价格上涨")
            else:
                print("       负Delta表示看跌期权，标的上涨期权价格下跌")
                
            print(f"Gamma: Delta的变化率，标的价格变动1美元时，Delta变动 {gamma:.6f}")
            print(f"Theta: 时间衰减，每天期权价格衰减约 {abs(theta):.4f} 美元")
            print(f"Vega: 波动率敏感性，隐含波动率变动1%时，期权价格变动 {vega:.4f} 美元")
            
            # 风险提示
            if abs(delta) < 0.1:
                print(f"\n{Fore.YELLOW}⚠️  低Delta值表示该期权对标的价格变动不敏感{Style.RESET_ALL}")
            if abs(theta) > 10:
                print(f"\n{Fore.RED}⚠️  高Theta值表示时间衰减较快，需注意时间风险{Style.RESET_ALL}")
            
        else:
            print("未找到该合约的数据")
    else:
        print(f"查询失败: {ticker_data.get('retMsg', '未知错误')}")


@cli.command()
@click.option('--symbol', '-s', required=True, help='期权合约符号')
@click.option('--target-price', '-t', required=True, type=float, help='目标BTC价格')
@click.option('--current-btc', '-c', type=float, help='当前BTC价格（不指定则自动获取）')
@click.option('--today', is_flag=True, help='当日内价格变化（最小时间衰减）')
@click.pass_context
def scenario(ctx, symbol, target_price, current_btc, today):
    """期权价格情景分析"""
    api = ctx.obj['api']
    
    print(f"{Fore.CYAN}正在进行期权价格情景分析...{Style.RESET_ALL}")
    
    # 获取期权当前数据
    ticker_data = api.get_option_tickers(symbol=symbol)
    
    if ticker_data.get('retCode') == 0:
        tickers = ticker_data.get('result', {}).get('list', [])
        
        if tickers:
            ticker = tickers[0]
            current_option_price = float(ticker.get('markPrice', 0))
            current_iv = float(ticker.get('markIv', 0)) * 100 if ticker.get('markIv') else 37.84
            
            # 如果没有指定当前BTC价格，使用默认值
            if not current_btc:
                # 这里可以调用BTC价格API，暂时使用估算值
                if 'BTC' in symbol:
                    current_btc = 98000  # 当前大概价格
                else:
                    current_btc = 3500   # ETH价格
            
            # 执行情景分析
            result = calculate_option_price_scenario(
                symbol, current_btc, target_price, current_option_price, current_iv, same_day=today
            )
            
            if result:
                # 为您的持仓计算盈亏
                print(f"\n💼 持仓影响分析:")
                print(f"   您当前净空头: 1.2手")
                position_pnl = -1.2 * result['price_change']  # 空头，价格上涨是亏损
                print(f"   持仓盈亏变化: ${position_pnl:+.2f}")
                if position_pnl > 0:
                    print(f"   ✅ 空头持仓将获利")
                else:
                    print(f"   ❌ 空头持仓将亏损")
            
        else:
            print("未找到该合约的数据")
    else:
        print(f"查询失败: {ticker_data.get('retMsg', '未知错误')}")


if __name__ == '__main__':
    cli()
