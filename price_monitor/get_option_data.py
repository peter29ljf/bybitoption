#!/usr/bin/env python3
"""
获取期权数据用于测试
"""
import sys
import os
import json
from datetime import datetime

# 添加父项目到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bybit_api import BybitAPI

def get_active_options():
    """获取活跃的期权合约"""
    api = BybitAPI()
    
    print("正在获取BTC期权数据...")
    
    # 获取期权链
    chain_data = api.get_option_chain('BTC', limit=100)
    
    if chain_data.get('retCode') != 0:
        print(f"获取期权链失败: {chain_data.get('retMsg', '未知错误')}")
        return None
    
    instruments = chain_data.get('result', {}).get('list', [])
    
    if not instruments:
        print("未找到期权合约")
        return None
    
    print(f"找到 {len(instruments)} 个期权合约")
    
    # 打印前几个合约的详细信息用于调试
    print("\n前5个合约详细信息:")
    for i, inst in enumerate(instruments[:5]):
        print(f"合约 {i+1}: {json.dumps(inst, indent=2, ensure_ascii=False)}")
    
    # 获取价格数据
    print("\n正在获取期权价格数据...")
    ticker_data = api.get_option_tickers(base_coin='BTC', limit=100)
    
    if ticker_data.get('retCode') != 0:
        print(f"获取价格数据失败: {ticker_data.get('retMsg', '未知错误')}")
        return None
    
    tickers = ticker_data.get('result', {}).get('list', [])
    print(f"找到 {len(tickers)} 个价格数据")
    
    # 打印前几个ticker的详细信息用于调试
    print("\n前3个价格数据详细信息:")
    for i, ticker in enumerate(tickers[:3]):
        print(f"价格 {i+1}: {json.dumps(ticker, indent=2, ensure_ascii=False)}")
    
    ticker_dict = {ticker['symbol']: ticker for ticker in tickers}
    
    # 筛选所有合约（不要求有成交量，只要有价格）
    active_options = []
    for instrument in instruments:
        symbol = instrument.get('symbol')
        if symbol in ticker_dict:
            ticker = ticker_dict[symbol]
            mark_price = ticker.get('markPrice')
            # 放宽条件，只要有标记价格就算
            if mark_price:
                try:
                    price_float = float(mark_price)
                    if price_float >= 0:  # 包括0价格的期权
                        active_options.append({
                            'symbol': symbol,
                            'expiry': instrument.get('deliveryTime'),
                            'strike': float(instrument.get('strikePrice', 0)),
                            'option_type': instrument.get('optionsType'),
                            'mark_price': price_float,
                            'bid_price': float(ticker.get('bid1Price', 0)),
                            'ask_price': float(ticker.get('ask1Price', 0)),
                            'volume_24h': float(ticker.get('volume24h', 0)),
                            'open_interest': float(ticker.get('openInterest', 0))
                        })
                except (ValueError, TypeError):
                    continue
    
    # 按标记价格排序，价格高的在前
    active_options.sort(key=lambda x: x['mark_price'], reverse=True)
    
    return active_options

def display_options(options, limit=10):
    """显示期权信息"""
    print(f"\n前 {limit} 个活跃期权合约:")
    print("-" * 120)
    print(f"{'序号':<4} {'合约符号':<25} {'类型':<6} {'执行价':<8} {'标记价格':<10} {'买价':<8} {'卖价':<8} {'24h成交量':<12} {'持仓量':<10}")
    print("-" * 120)
    
    for i, option in enumerate(options[:limit], 1):
        print(f"{i:<4} {option['symbol']:<25} {option['option_type']:<6} {option['strike']:<8.0f} "
              f"{option['mark_price']:<10.4f} {option['bid_price']:<8.4f} {option['ask_price']:<8.4f} "
              f"{option['volume_24h']:<12.2f} {option['open_interest']:<10.2f}")

def suggest_test_option(options):
    """建议测试用的期权"""
    # 选择价格合理的期权（放宽条件，适应测试网环境）
    suitable_options = [
        opt for opt in options 
        if opt['mark_price'] > 50  # 选择价格大于50的期权便于测试
    ]
    
    if not suitable_options:
        # 如果没有找到高价期权，选择任何有价格的期权
        suitable_options = [opt for opt in options if opt['mark_price'] > 0]
    
    if suitable_options:
        best_option = suitable_options[0]
        
        print(f"\n🎯 建议测试期权:")
        print(f"合约符号: {best_option['symbol']}")
        print(f"当前标记价格: {best_option['mark_price']:.4f}")
        print(f"建议目标价格 (+3%): {best_option['mark_price'] * 1.03:.4f}")
        print(f"建议目标价格 (-3%): {best_option['mark_price'] * 0.97:.4f}")
        print(f"24h成交量: {best_option['volume_24h']:.2f}")
        print(f"持仓量: {best_option['open_interest']:.2f}")
        
        return best_option
    
    # 如果还是没有，手动创建一个测试期权
    if options:
        test_option = options[0]
        # 手动设置一个测试价格
        test_option['mark_price'] = 1000.0
        print(f"\n🎯 测试期权 (手动设置价格):")
        print(f"合约符号: {test_option['symbol']}")
        print(f"测试标记价格: {test_option['mark_price']:.4f}")
        print(f"建议目标价格 (+3%): {test_option['mark_price'] * 1.03:.4f}")
        print(f"建议目标价格 (-3%): {test_option['mark_price'] * 0.97:.4f}")
        return test_option
    
    return None

def main():
    """主函数"""
    print("=" * 60)
    print("期权数据获取工具")
    print("=" * 60)
    
    try:
        options = get_active_options()
        
        if options:
            display_options(options)
            best_option = suggest_test_option(options)
            
            if best_option:
                print(f"\n📋 测试参数建议:")
                print(f"task_id: test_monitor_{int(datetime.now().timestamp())}")
                print(f"option_symbol: {best_option['symbol']}")
                print(f"target_price: {best_option['mark_price'] * 1.03:.4f} (上穿测试)")
                print(f"target_price: {best_option['mark_price'] * 0.97:.4f} (下穿测试)")
                print(f"webhook_url: https://httpbin.org/post")
                
                # 生成测试用的curl命令
                print(f"\n🚀 测试命令 (上穿):")
                test_data_up = {
                    "task_id": f"test_up_{int(datetime.now().timestamp())}",
                    "option_symbol": best_option['symbol'],
                    "target_price": round(best_option['mark_price'] * 1.03, 4),
                    "webhook_url": "https://httpbin.org/post",
                    "timeout_hours": 2
                }
                
                print("curl -X POST http://localhost:8888/api/monitor/create \\")
                print("  -H 'Content-Type: application/json' \\")
                print(f"  -d '{json.dumps(test_data_up)}'")
                
                print(f"\n🚀 测试命令 (下穿):")
                test_data_down = {
                    "task_id": f"test_down_{int(datetime.now().timestamp())}",
                    "option_symbol": best_option['symbol'],
                    "target_price": round(best_option['mark_price'] * 0.97, 4),
                    "webhook_url": "https://httpbin.org/post",
                    "timeout_hours": 2
                }
                
                print("curl -X POST http://localhost:8888/api/monitor/create \\")
                print("  -H 'Content-Type: application/json' \\")
                print(f"  -d '{json.dumps(test_data_down)}'")
        else:
            print("未获取到期权数据")
            
    except Exception as e:
        print(f"获取数据时发生错误: {e}")

if __name__ == "__main__":
    main()
