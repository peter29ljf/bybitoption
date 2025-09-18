#!/usr/bin/env python3
"""
Bybit期权链搜索Web应用
"""
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import json
from bybit_api import BybitAPI
from option_chain import OptionChain
from config import Config
from data_cache import data_cache
from ai_assistant import ai_assistant
from trading import OptionTrader
from strategy_manager import strategy_service
from strategy_manager.api import bp as strategies_bp
from strategy_manager.monitor_client import monitor_client
from settings_manager import settings_manager
from settings_manager.manager import AppSettings
from settings_manager.api import bp as settings_bp
from watchlist_manager import watchlist_manager
from threading import Lock
from typing import Optional, Dict, List

app = Flask(__name__)

current_settings: AppSettings = settings_manager.get_settings()


def apply_runtime_settings(settings: AppSettings) -> None:
    """Apply runtime API credentials and external service configuration."""
    base_url = 'https://api-testnet.bybit.com' if settings.is_testnet else 'https://api.bybit.com'

    Config.BYBIT_API_KEY = settings.api_key
    Config.BYBIT_API_SECRET = settings.api_secret
    Config.BYBIT_TESTNET = settings.is_testnet
    Config.BYBIT_BASE_URL = base_url
    Config.PRICE_MONITOR_BASE = settings.price_monitor_base
    Config.STRATEGY_WEBHOOK_BASE = settings.strategy_webhook_base

    global api_client, option_chain, strategy_trader, current_settings
    current_settings = settings

    api_client = BybitAPI(
        api_key=settings.api_key,
        api_secret=settings.api_secret,
        base_url=base_url,
    )
    option_chain = OptionChain(api_client)
    data_cache.api_client = api_client
    strategy_trader = OptionTrader(api_client)

    app.config['STRATEGY_TRADER'] = strategy_trader
    app.config['PRICE_MONITOR_BASE'] = settings.price_monitor_base
    app.config['STRATEGY_WEBHOOK_BASE'] = settings.strategy_webhook_base

    monitor_client.base_url = settings.price_monitor_base


apply_runtime_settings(current_settings)

# 关注列表持久化
watchlist_lock = Lock()
watchlist = []


def _load_watchlist_from_disk():
    items = watchlist_manager.load()
    if items:
        watchlist.extend(items)


_load_watchlist_from_disk()


def serialize_option_for_watchlist(option: dict) -> dict:
    """提取关注列表所需的字段，保持返回结构一致"""
    return {
        'symbol': option.get('symbol'),
        'base_coin': option.get('base_coin'),
        'option_type': option.get('option_type'),
        'strike_price': option.get('strike_price'),
        'expiry_date': option.get('expiry_date'),
        'expiry_date_formatted': option.get('expiry_date_formatted'),
        'days_to_expiry': option.get('days_to_expiry'),
        'bid_price': option.get('bid_price'),
        'ask_price': option.get('ask_price'),
        'mark_price': option.get('mark_price'),
        'iv': option.get('iv'),
        'delta': option.get('delta'),
        'volume_24h': option.get('volume_24h'),
        'open_interest': option.get('open_interest'),
        'price_diff': option.get('price_diff'),
        'price_diff_pct': option.get('price_diff_pct'),
        'in_the_money': option.get('in_the_money'),
        'added_at': datetime.utcnow().isoformat() + 'Z'
    }


def _get_cached_option(symbol: str, base_coin: str) -> Optional[dict]:
    """在缓存中查找指定合约"""
    if not symbol:
        return None

    options = data_cache.get_cached_options(base_coin)
    for option in options:
        if option.get('symbol') == symbol:
            return option
    return None


def _format_expiry_details(expiry_timestamp: Optional[int]) -> Dict[str, Optional[int]]:
    """根据到期时间戳计算显示字段"""
    if not expiry_timestamp:
        return {
            'expiry_date': None,
            'expiry_date_formatted': None,
            'days_to_expiry': None
        }

    try:
        expiry_dt = datetime.fromtimestamp(int(expiry_timestamp) / 1000)
    except (ValueError, TypeError, OSError):
        return {
            'expiry_date': expiry_timestamp,
            'expiry_date_formatted': None,
            'days_to_expiry': None
        }

    days_to_expiry = (expiry_dt - datetime.now()).days

    return {
        'expiry_date': int(expiry_timestamp),
        'expiry_date_formatted': expiry_dt.strftime('%Y-%m-%d %H:%M'),
        'days_to_expiry': days_to_expiry
    }


def _refresh_watchlist_entry(entry: dict) -> dict:
    """使用最新缓存数据更新关注项"""
    symbol = entry.get('symbol')
    base_coin = entry.get('base_coin', 'BTC')

    cached_option = _get_cached_option(symbol, base_coin)

    if cached_option:
        expiry_details = _format_expiry_details(cached_option.get('expiry_date'))
        entry.update({
            'strike_price': cached_option.get('strike_price', entry.get('strike_price')),
            'option_type': cached_option.get('option_type', entry.get('option_type')),
            'base_coin': cached_option.get('base_coin', base_coin),
            'bid_price': cached_option.get('bid_price'),
            'ask_price': cached_option.get('ask_price'),
            'mark_price': cached_option.get('mark_price'),
            'last_price': cached_option.get('last_price'),
            'volume_24h': cached_option.get('volume_24h'),
            'open_interest': cached_option.get('open_interest'),
            'iv': cached_option.get('iv'),
            'delta': cached_option.get('delta'),
            **expiry_details,
            'stale': False,
            'last_updated': datetime.utcnow().isoformat() + 'Z'
        })
    else:
        entry.setdefault('base_coin', base_coin)
        entry['stale'] = True
        entry['last_updated'] = datetime.utcnow().isoformat() + 'Z'

    return entry


def _get_watchlist_items_locked() -> List[dict]:
    """刷新并返回关注列表数据（调用者需持有锁）"""
    updated_items: List[dict] = []
    for index, item in enumerate(watchlist):
        refreshed = _refresh_watchlist_entry(item)
        watchlist[index] = refreshed
        updated_items.append(dict(refreshed))  # 返回浅拷贝以避免外部修改
    return updated_items

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


# 注册设置与策略管理API
app.extensions['settings_apply_callback'] = apply_runtime_settings
app.register_blueprint(settings_bp)
app.register_blueprint(strategies_bp)
strategy_service.init_app(app)

@app.route('/search_options', methods=['POST'])
def search_options():
    """搜索期权（使用缓存数据）"""
    try:
        data = request.get_json()
        
        # 获取搜索参数
        direction = data.get('direction', 'Call')  # Call 或 Put
        target_price = float(data.get('target_price', 0))
        days = int(data.get('days', 0))
        base_coin = data.get('base_coin', 'BTC')
        
        print(f"搜索参数: 方向={direction}, 目标价格={target_price}, 天数={days}, 基础币={base_coin}")
        
        # 从缓存获取期权数据
        cached_options = data_cache.get_cached_options(base_coin)
        
        if not cached_options:
            return jsonify({
                'success': False,
                'message': '暂无缓存数据，请先刷新数据'
            })
        
        # 计算目标日期范围（正负10天）
        target_date = datetime.now() + timedelta(days=days)
        start_date = target_date - timedelta(days=10)
        end_date = target_date + timedelta(days=10)
        
        # 筛选符合条件的期权
        filtered_options = []
        
        for option in cached_options:
            # 筛选期权类型
            if option['option_type'] != direction:
                continue
                
            # 解析到期时间
            expiry_timestamp = int(option['expiry_date']) / 1000
            expiry_date = datetime.fromtimestamp(expiry_timestamp)
            
            # 筛选时间范围
            if not (start_date <= expiry_date <= end_date):
                continue
            
            # 计算到期天数
            days_to_expiry = (expiry_date - datetime.now()).days
            
            # 计算价格与目标价格的差距
            strike_price = option['strike_price']
            price_diff = abs(strike_price - target_price)
            price_diff_pct = (price_diff / target_price * 100) if target_price > 0 else 0
            
            # 添加计算的字段
            option_result = option.copy()
            option_result['expiry_date_formatted'] = expiry_date.strftime('%Y-%m-%d %H:%M')
            option_result['days_to_expiry'] = days_to_expiry
            option_result['price_diff'] = price_diff
            option_result['price_diff_pct'] = price_diff_pct
            option_result['base_coin'] = base_coin
            
            # 判断期权是否价内
            if direction == 'Call':
                option_result['in_the_money'] = strike_price < target_price
            else:  # Put
                option_result['in_the_money'] = strike_price > target_price
                
            filtered_options.append(option_result)
        
        # 按价格差距排序
        filtered_options.sort(key=lambda x: x['price_diff'])
        
        # 限制返回结果数量
        filtered_options = filtered_options[:50]
        
        return jsonify({
            'success': True,
            'options': filtered_options,
            'total_count': len(filtered_options),
            'search_params': {
                'direction': direction,
                'target_price': target_price,
                'days': days,
                'base_coin': base_coin,
                'date_range': f"{start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}"
            }
        })
        
    except Exception as e:
        print(f"搜索期权时出错: {e}")
        return jsonify({
            'success': False,
            'message': f'搜索失败: {str(e)}'
        })

@app.route('/get_current_price/<base_coin>')
def get_current_price(base_coin):
    """获取当前价格（模拟接口）"""
    try:
        # 这里可以调用实际的价格API
        # 暂时返回模拟价格
        prices = {
            'BTC': 98000,
            'ETH': 3500
        }
        
        current_price = prices.get(base_coin.upper(), 0)
        
        return jsonify({
            'success': True,
            'price': current_price,
            'symbol': base_coin.upper()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/get_strike_prices/<base_coin>')
def get_strike_prices(base_coin):
    """获取可用的执行价格（从缓存）"""
    try:
        # 从缓存获取执行价格
        strike_prices = data_cache.get_cached_strike_prices(base_coin)
        
        if not strike_prices:
            return jsonify({
                'success': False,
                'message': '暂无缓存数据，请先刷新数据'
            })
        
        # 获取当前价格作为参考
        current_price = 98000 if base_coin == 'BTC' else 3500
        
        strike_list = []
        for strike in strike_prices:
            # 计算与当前价格的差距
            diff = strike - current_price
            diff_pct = (diff / current_price * 100) if current_price > 0 else 0
            
            # 判断价内价外状态
            if abs(diff_pct) <= 5:
                status = 'ATM'  # At The Money
            elif diff > 0:
                status = 'OTM'  # Out of The Money
            else:
                status = 'ITM'  # In The Money
            
            strike_list.append({
                'price': strike,
                'formatted': f"${strike:,.0f}",
                'diff': diff,
                'diff_pct': diff_pct,
                'status': status
            })
        
        return jsonify({
            'success': True,
            'strikes': strike_list,
            'current_price': current_price,
            'total_count': len(strike_list)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/refresh_data/<base_coin>')
def refresh_data(base_coin):
    """刷新期权数据"""
    try:
        result = data_cache.refresh_option_data(base_coin)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'刷新数据失败: {str(e)}'
        })

@app.route('/get_cache_status/<base_coin>')
def get_cache_status(base_coin):
    """获取缓存状态"""
    try:
        status = data_cache.get_cache_status(base_coin)
        return jsonify({
            'success': True,
            **status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/get_expiry_dates/<base_coin>')
def get_expiry_dates(base_coin):
    """获取可用的到期日期（从缓存）"""
    try:
        # 从缓存获取到期时间戳
        expiry_timestamps = data_cache.get_cached_expiry_dates(base_coin)
        
        if not expiry_timestamps:
            return jsonify({
                'success': False,
                'message': '暂无缓存数据，请先刷新数据'
            })
        
        # 计算每个日期距离现在的天数
        today = datetime.now()
        dates_with_days = []
        
        for timestamp in expiry_timestamps:
            expiry_date = datetime.fromtimestamp(timestamp / 1000)
            days_diff = (expiry_date - today).days
            
            # 只显示未到期的合约
            if days_diff >= 0:
                dates_with_days.append({
                    'date': expiry_date.strftime('%Y-%m-%d'),
                    'datetime': expiry_date.strftime('%Y-%m-%d %H:%M'),
                    'days': days_diff,
                    'formatted': f"{expiry_date.strftime('%Y-%m-%d')} ({days_diff}天)",
                    'timestamp': timestamp
                })
        
        return jsonify({
            'success': True,
            'dates': dates_with_days,
            'total_count': len(dates_with_days)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })


@app.route('/watchlist', methods=['GET'])
def get_watchlist():
    """获取关注列表"""
    with watchlist_lock:
        items = _get_watchlist_items_locked()
        watchlist_manager.save(items)

    return jsonify({
        'success': True,
        'watchlist': items,
        'count': len(items)
    })


@app.route('/watchlist', methods=['POST'])
def add_to_watchlist():
    """将期权加入关注列表"""
    try:
        data = request.get_json() or {}
        option = data.get('option') or {}
        symbol = option.get('symbol')

        if not symbol:
            return jsonify({
                'success': False,
                'message': '缺少必要的合约代码信息'
            }), 400

        watchlist_item = serialize_option_for_watchlist(option)

        with watchlist_lock:
            for index, item in enumerate(watchlist):
                if item.get('symbol') == symbol:
                    watchlist[index] = watchlist_item
                    break
            else:
                watchlist.append(watchlist_item)
            items = _get_watchlist_items_locked()
            watchlist_manager.save(items)

        return jsonify({
            'success': True,
            'message': f'{symbol} 已加入关注列表',
            'watchlist': items
        })
    except Exception as exc:
        return jsonify({
            'success': False,
            'message': f'加入关注列表失败: {exc}'
        }), 500


@app.route('/watchlist', methods=['DELETE'])
def clear_watchlist():
    """清空关注列表"""
    with watchlist_lock:
        watchlist.clear()
        watchlist_manager.clear()

    return jsonify({
        'success': True,
        'message': '关注列表已清空'
    })

# AI助手相关接口
@app.route('/ai/config/<provider>', methods=['GET', 'POST'])
def ai_config(provider):
    """AI助手配置"""
    if request.method == 'GET':
        # 获取配置
        config = ai_assistant.get_api_config(provider)
        # 隐藏API密钥
        if 'api_key' in config:
            config['api_key'] = '***' if config['api_key'] else ''
        return jsonify({
            'success': True,
            'config': config
        })
    else:
        # 更新配置
        try:
            data = request.get_json()
            success = ai_assistant.update_api_config(provider, data)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'{provider} 配置更新成功'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '不支持的AI服务提供商'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'配置更新失败: {str(e)}'
            })

@app.route('/ai/test/<provider>')
def ai_test_connection(provider):
    """测试AI服务连接"""
    try:
        result = ai_assistant.test_api_connection(provider)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'测试连接失败: {str(e)}'
        })

@app.route('/ai/chat/<provider>', methods=['POST'])
def ai_chat(provider):
    """AI对话"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        context = data.get('context', {})
        
        if not user_message.strip():
            return jsonify({
                'success': False,
                'message': '消息内容不能为空'
            })
        
        result = ai_assistant.chat(provider, user_message, context)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'对话失败: {str(e)}'
        })

@app.route('/ai/analyze/<provider>', methods=['POST'])
def ai_analyze_options(provider):
    """AI分析期权数据"""
    try:
        data = request.get_json()
        user_query = data.get('query', '请分析这些期权数据并给出交易建议')
        search_params = data.get('search_params', {})
        
        # 获取当前搜索的期权数据
        base_coin = search_params.get('base_coin', 'BTC')
        direction = search_params.get('direction', 'Call')
        target_price = float(search_params.get('target_price', 0))
        days = int(search_params.get('days', 0))
        
        # 从缓存获取期权数据并进行筛选
        cached_options = data_cache.get_cached_options(base_coin)
        
        if not cached_options:
            return jsonify({
                'success': False,
                'message': '暂无期权数据，请先刷新数据'
            })
        
        # 计算目标日期范围（正负10天）
        target_date = datetime.now() + timedelta(days=days)
        start_date = target_date - timedelta(days=10)
        end_date = target_date + timedelta(days=10)
        
        # 筛选符合条件的期权
        filtered_options = []
        
        for option in cached_options:
            # 筛选期权类型
            if option['option_type'] != direction:
                continue
                
            # 解析到期时间
            expiry_timestamp = int(option['expiry_date']) / 1000
            expiry_date = datetime.fromtimestamp(expiry_timestamp)
            
            # 筛选时间范围
            if not (start_date <= expiry_date <= end_date):
                continue
            
            # 计算额外字段
            days_to_expiry = (expiry_date - datetime.now()).days
            strike_price = option['strike_price']
            price_diff = abs(strike_price - target_price)
            price_diff_pct = (price_diff / target_price * 100) if target_price > 0 else 0
            
            # 添加计算的字段
            option_result = option.copy()
            option_result['expiry_date_formatted'] = expiry_date.strftime('%Y-%m-%d %H:%M')
            option_result['days_to_expiry'] = days_to_expiry
            option_result['price_diff'] = price_diff
            option_result['price_diff_pct'] = price_diff_pct
            
            # 判断价内价外
            if direction == 'Call':
                option_result['in_the_money'] = strike_price < target_price
            else:
                option_result['in_the_money'] = strike_price > target_price
                
            filtered_options.append(option_result)
        
        # 按价格差距排序，取前20个
        filtered_options.sort(key=lambda x: x['price_diff'])
        analysis_data = filtered_options[:20]
        
        if not analysis_data:
            return jsonify({
                'success': False,
                'message': '没有找到符合条件的期权数据'
            })
        
        # 调用AI分析
        result = ai_assistant.analyze_options_data(provider, analysis_data, user_query)
        
        # 如果分析成功，生成任务清单
        if result.get('success'):
            tasks = ai_assistant.generate_trading_tasks(result.get('response', ''))
            result['tasks'] = tasks
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'分析失败: {str(e)}'
        })

@app.route('/ai/history')
def ai_conversation_history():
    """获取对话历史"""
    try:
        history = ai_assistant.get_conversation_history()
        return jsonify({
            'success': True,
            'history': history
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取历史失败: {str(e)}'
        })

@app.route('/ai/clear_history', methods=['POST'])
def ai_clear_history():
    """清除对话历史"""
    try:
        ai_assistant.clear_conversation_history()
        return jsonify({
            'success': True,
            'message': '对话历史已清除'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'清除历史失败: {str(e)}'
        })

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    print("启动Bybit期权链搜索Web应用...")
    print(f"API配置: {'已设置' if api_client.api_key else '未设置'}")
    print(f"环境: {'测试网' if Config.BYBIT_TESTNET else '生产环境'}")
    print("访问地址: http://localhost:8080")
    
    app.run(debug=True, host='0.0.0.0', port=8080)
