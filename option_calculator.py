"""
期权定价计算器
使用 Black-Scholes 模型估算期权价格
"""
import math
from scipy.stats import norm
from datetime import datetime, timedelta
from typing import Dict, Optional


class OptionCalculator:
    """期权定价计算器"""
    
    @staticmethod
    def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> Dict[str, float]:
        """
        Black-Scholes 看涨期权定价公式
        
        参数:
        S: 当前标的价格
        K: 执行价格
        T: 到期时间（年）
        r: 无风险利率
        sigma: 波动率
        
        返回:
        包含期权价格和希腊字母的字典
        """
        # 计算 d1 和 d2
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        # 标准正态分布累积分布函数
        N_d1 = norm.cdf(d1)
        N_d2 = norm.cdf(d2)
        
        # 标准正态分布概率密度函数
        phi_d1 = norm.pdf(d1)
        
        # 期权价格
        call_price = S * N_d1 - K * math.exp(-r * T) * N_d2
        
        # 希腊字母
        delta = N_d1
        gamma = phi_d1 / (S * sigma * math.sqrt(T))
        theta = -(S * phi_d1 * sigma / (2 * math.sqrt(T)) + 
                 r * K * math.exp(-r * T) * N_d2) / 365  # 转换为每日
        vega = S * phi_d1 * math.sqrt(T) / 100  # 除以100得到1%变化的影响
        
        return {
            'price': max(call_price, 0),  # 期权价格不能为负
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'd1': d1,
            'd2': d2
        }
    
    @staticmethod
    def calculate_time_to_expiry(expiry_date_str: str) -> float:
        """计算到期时间（年）"""
        # 解析到期日期，格式如 "31OCT25"
        try:
            # 转换月份缩写
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            
            day = int(expiry_date_str[:2])
            month_str = expiry_date_str[2:5]
            year = 2000 + int(expiry_date_str[5:7])
            
            month = month_map[month_str]
            
            expiry_date = datetime(year, month, day, 8, 0)  # 假设8点到期
            current_date = datetime.now()
            
            time_diff = expiry_date - current_date
            time_to_expiry = time_diff.total_seconds() / (365.25 * 24 * 3600)
            
            return max(time_to_expiry, 0)  # 不能为负
            
        except:
            # 如果解析失败，返回默认值
            return 0.1
    
    @staticmethod
    def implied_volatility_from_current_data(current_price: float, S: float, K: float, 
                                           T: float, r: float = 0.05) -> float:
        """
        从当前期权价格反推隐含波动率
        使用牛顿-拉夫逊方法
        """
        # 初始猜测
        sigma = 0.3
        tolerance = 1e-6
        max_iterations = 100
        
        for i in range(max_iterations):
            # 计算当前sigma下的期权价格
            bs_result = OptionCalculator.black_scholes_call(S, K, T, r, sigma)
            price_diff = bs_result['price'] - current_price
            
            if abs(price_diff) < tolerance:
                return sigma
            
            # Vega (价格对波动率的导数)
            vega = bs_result['vega'] * 100  # 转换回原始单位
            
            if abs(vega) < tolerance:
                break
                
            # 牛顿-拉夫逊更新
            sigma = sigma - price_diff / vega
            
            # 确保sigma在合理范围内
            sigma = max(0.01, min(sigma, 5.0))
        
        return sigma


def calculate_option_price_scenario(symbol: str, current_btc: float, target_btc: float, 
                                  current_option_price: float, current_iv: float, 
                                  same_day: bool = False):
    """计算期权价格情景分析"""
    
    print(f"\n📊 期权价格情景分析: {symbol}")
    print(f"当前BTC价格: ${current_btc:,.0f}")
    print(f"目标BTC价格: ${target_btc:,.0f}")
    print(f"当前期权价格: ${current_option_price:.2f}")
    print(f"当前隐含波动率: {current_iv:.2f}%")
    
    # 解析期权信息
    parts = symbol.split('-')
    if len(parts) >= 3:
        expiry_str = parts[1]  # "31OCT25"
        strike_str = parts[2]  # "117000"
        
        try:
            strike_price = float(strike_str)
            
            # 计算到期时间
            calc = OptionCalculator()
            time_to_expiry = calc.calculate_time_to_expiry(expiry_str)
            
            # 如果是当日价格变化，时间几乎不变
            if same_day:
                # 减去几个小时的时间衰减，假设是交易日中的价格变化
                hours_passed = 8  # 假设8小时内发生价格变化
                time_reduction = hours_passed / (365.25 * 24)
                adjusted_time = max(time_to_expiry - time_reduction, 0.001)  # 最小保留0.001年
                print(f"执行价格: ${strike_price:,.0f}")
                print(f"原到期时间: {time_to_expiry:.3f} 年 ({time_to_expiry * 365:.0f} 天)")
                print(f"调整后时间: {adjusted_time:.3f} 年 (当日内价格变化)")
                time_to_expiry = adjusted_time
            else:
                print(f"执行价格: ${strike_price:,.0f}")
                print(f"到期时间: {time_to_expiry:.3f} 年 ({time_to_expiry * 365:.0f} 天)")
            
            # 参数设置
            risk_free_rate = 0.05  # 5% 无风险利率
            current_sigma = current_iv / 100  # 转换为小数
            
            # 情景1: 维持当前波动率
            scenario1 = calc.black_scholes_call(
                target_btc, strike_price, time_to_expiry, risk_free_rate, current_sigma
            )
            
            # 情景2: 波动率上升（价格大幅变动时常见）
            high_iv = current_sigma * 1.2  # 波动率上升20%
            scenario2 = calc.black_scholes_call(
                target_btc, strike_price, time_to_expiry, risk_free_rate, high_iv
            )
            
            # 情景3: 波动率下降
            low_iv = current_sigma * 0.8  # 波动率下降20%
            scenario3 = calc.black_scholes_call(
                target_btc, strike_price, time_to_expiry, risk_free_rate, low_iv
            )
            
            time_desc = "当日内" if same_day else "未来某时"
            print(f"\n🎯 BTC{time_desc}价格达到 ${target_btc:,.0f} 时的期权价格预估:")
            print(f"{'='*60}")
            
            if same_day:
                print(f"⏰ 注意: 此为当日内价格变化分析，时间衰减影响最小")
            
            print(f"\n📈 情景1 - 波动率维持 {current_iv:.1f}%:")
            print(f"   期权价格: ${scenario1['price']:.2f}")
            print(f"   Delta: {scenario1['delta']:.4f}")
            print(f"   Gamma: {scenario1['gamma']:.6f}")
            print(f"   Theta: ${scenario1['theta']:.2f}/天")
            print(f"   Vega: ${scenario1['vega']:.2f}")
            
            print(f"\n📊 情景2 - 波动率上升至 {high_iv*100:.1f}%:")
            print(f"   期权价格: ${scenario2['price']:.2f}")
            print(f"   Delta: {scenario2['delta']:.4f}")
            
            print(f"\n📉 情景3 - 波动率下降至 {low_iv*100:.1f}%:")
            print(f"   期权价格: ${scenario3['price']:.2f}")
            print(f"   Delta: {scenario3['delta']:.4f}")
            
            # 计算变化
            price_change1 = scenario1['price'] - current_option_price
            price_change_pct1 = (price_change1 / current_option_price) * 100
            
            print(f"\n💰 价格变化分析 (基准情景):")
            print(f"   价格变化: ${price_change1:+.2f}")
            print(f"   变化百分比: {price_change_pct1:+.1f}%")
            
            # 内在价值分析
            intrinsic_value = max(target_btc - strike_price, 0)
            time_value1 = scenario1['price'] - intrinsic_value
            
            print(f"\n🔍 价值分解:")
            print(f"   内在价值: ${intrinsic_value:.2f}")
            print(f"   时间价值: ${time_value1:.2f}")
            
            if target_btc > strike_price:
                print(f"   ✅ 期权为实值 (ITM)")
                moneyness = (target_btc - strike_price) / strike_price * 100
                print(f"   实值程度: {moneyness:.1f}%")
            else:
                print(f"   ❌ 期权仍为虚值 (OTM)")
                otm_amount = strike_price - target_btc
                print(f"   需要再涨: ${otm_amount:,.0f}")
            
            return {
                'base_scenario': scenario1['price'],
                'high_iv_scenario': scenario2['price'],
                'low_iv_scenario': scenario3['price'],
                'price_change': price_change1,
                'price_change_pct': price_change_pct1,
                'intrinsic_value': intrinsic_value,
                'time_value': time_value1
            }
            
        except Exception as e:
            print(f"计算错误: {e}")
            return None
    else:
        print("无法解析期权符号")
        return None


if __name__ == "__main__":
    # 测试
    result = calculate_option_price_scenario(
        "BTC-31OCT25-117000-C-USDT",
        98000,  # 当前BTC价格
        107000,  # 目标BTC价格
        3860,   # 当前期权价格
        37.84   # 当前隐含波动率
    )
