"""
AI助手模块
支持Claude API, Ollama, DeepSeek API
用于期权数据分析和交易建议
"""
import json
import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import os

class AIAssistant:
    """AI助手管理器"""
    
    def __init__(self):
        """初始化AI助手"""
        self.conversation_history = []
        self.api_configs = {
            'claude': {
                'api_key': '',
                'base_url': 'https://api.anthropic.com',
                'model': 'claude-3-sonnet-20240229',
                'max_tokens': 4000
            },
            'ollama': {
                'base_url': 'http://localhost:11434',
                'model': 'llama2:7b',
                'temperature': 0.7
            },
            'deepseek': {
                'api_key': '',
                'base_url': 'https://api.deepseek.com',
                'model': 'deepseek-chat',
                'max_tokens': 4000
            }
        }
        
    def update_api_config(self, provider: str, config: Dict):
        """更新API配置"""
        if provider in self.api_configs:
            self.api_configs[provider].update(config)
            return True
        return False
    
    def get_api_config(self, provider: str) -> Dict:
        """获取API配置"""
        return self.api_configs.get(provider, {})
    
    def test_api_connection(self, provider: str) -> Dict:
        """测试API连接"""
        try:
            if provider == 'claude':
                return self._test_claude_connection()
            elif provider == 'ollama':
                return self._test_ollama_connection()
            elif provider == 'deepseek':
                return self._test_deepseek_connection()
            else:
                return {'success': False, 'message': '不支持的AI服务提供商'}
                
        except Exception as e:
            return {'success': False, 'message': f'连接测试失败: {str(e)}'}
    
    def _test_claude_connection(self) -> Dict:
        """测试Claude API连接"""
        config = self.api_configs['claude']
        if not config.get('api_key'):
            return {'success': False, 'message': '请设置Claude API Key'}
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': config['api_key'],
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': config['model'],
            'max_tokens': 100,
            'messages': [{'role': 'user', 'content': 'Hello, are you working?'}]
        }
        
        try:
            response = requests.post(
                f"{config['base_url']}/v1/messages",
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Claude API连接成功'}
            else:
                return {'success': False, 'message': f'Claude API错误: {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'message': f'Claude API连接失败: {str(e)}'}
    
    def _test_ollama_connection(self) -> Dict:
        """测试Ollama连接"""
        config = self.api_configs['ollama']
        
        try:
            # 测试Ollama服务是否运行
            response = requests.get(f"{config['base_url']}/api/tags", timeout=5)
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                if models:
                    return {'success': True, 'message': f'Ollama连接成功，可用模型: {len(models)}个'}
                else:
                    return {'success': False, 'message': 'Ollama运行中但无可用模型'}
            else:
                return {'success': False, 'message': 'Ollama服务未响应'}
                
        except requests.RequestException:
            return {'success': False, 'message': 'Ollama服务未启动或无法连接'}
    
    def _test_deepseek_connection(self) -> Dict:
        """测试DeepSeek API连接"""
        config = self.api_configs['deepseek']
        if not config.get('api_key'):
            return {'success': False, 'message': '请设置DeepSeek API Key'}
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {config['api_key']}"
        }
        
        data = {
            'model': config['model'],
            'messages': [{'role': 'user', 'content': 'Hello'}],
            'max_tokens': 100
        }
        
        try:
            response = requests.post(
                f"{config['base_url']}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return {'success': True, 'message': 'DeepSeek API连接成功'}
            else:
                return {'success': False, 'message': f'DeepSeek API错误: {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'message': f'DeepSeek API连接失败: {str(e)}'}
    
    def analyze_options_data(self, provider: str, options_data: List[Dict], user_query: str) -> Dict:
        """分析期权数据"""
        try:
            # 准备分析提示词
            analysis_prompt = self._build_analysis_prompt(options_data, user_query)
            
            # 根据提供商调用相应的API
            if provider == 'claude':
                return self._call_claude_api(analysis_prompt)
            elif provider == 'ollama':
                return self._call_ollama_api(analysis_prompt)
            elif provider == 'deepseek':
                return self._call_deepseek_api(analysis_prompt)
            else:
                return {'success': False, 'message': '不支持的AI服务提供商'}
                
        except Exception as e:
            return {'success': False, 'message': f'分析失败: {str(e)}'}
    
    def _build_analysis_prompt(self, options_data: List[Dict], user_query: str) -> str:
        """构建分析提示词"""
        # 准备期权数据摘要
        data_summary = {
            'total_contracts': len(options_data),
            'expiry_dates': list(set([opt.get('expiry_date_formatted', '') for opt in options_data])),
            'strike_prices': list(set([opt.get('strike_price', 0) for opt in options_data])),
            'option_types': list(set([opt.get('option_type', '') for opt in options_data]))
        }
        
        # 选择前10个最相关的期权合约作为样本
        sample_contracts = options_data[:10]
        
        prompt = f"""
你是一位专业的期权交易分析师。用户咨询: {user_query}

以下是当前的期权数据:

数据概览:
- 总合约数: {data_summary['total_contracts']}
- 可用到期日: {', '.join(data_summary['expiry_dates'][:5])}
- 执行价格范围: {min(data_summary['strike_prices']):.0f} - {max(data_summary['strike_prices']):.0f}
- 期权类型: {', '.join(data_summary['option_types'])}

样本合约详情:
"""
        
        for i, contract in enumerate(sample_contracts, 1):
            prompt += f"""
合约 {i}:
- 代码: {contract.get('symbol', '')}
- 类型: {contract.get('option_type', '')}
- 执行价: ${contract.get('strike_price', 0):,.0f}
- 到期日: {contract.get('expiry_date_formatted', '')}
- 剩余天数: {contract.get('days_to_expiry', 0)}天
- 标记价格: ${contract.get('mark_price', 0):.4f}
- 买卖价差: ${contract.get('bid_price', 0):.4f} - ${contract.get('ask_price', 0):.4f}
- 隐含波动率: {contract.get('iv', 0):.1f}%
- Delta: {contract.get('delta', 0):.4f}
- 成交量: {contract.get('volume_24h', 0):.0f}
- 持仓量: {contract.get('open_interest', 0):.0f}
- 价内状态: {'价内' if contract.get('in_the_money', False) else '价外'}
"""
        
        prompt += """

请基于以上数据，提供专业的期权分析和建议。请包括:

1. 市场概况分析
2. 推荐的期权合约（说明理由）
3. 风险评估
4. 具体的交易建议（包括进入点、止损点、目标利润）
5. 市场时机分析

请用简洁明了的中文回答，重点突出实用的交易建议。
"""
        
        return prompt
    
    def _call_claude_api(self, prompt: str) -> Dict:
        """调用Claude API"""
        config = self.api_configs['claude']
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': config['api_key'],
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': config['model'],
            'max_tokens': config['max_tokens'],
            'messages': [{'role': 'user', 'content': prompt}]
        }
        
        try:
            response = requests.post(
                f"{config['base_url']}/v1/messages",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                
                # 添加到对话历史
                self.conversation_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'provider': 'claude',
                    'user_input': prompt,
                    'ai_response': content
                })
                
                return {
                    'success': True,
                    'response': content,
                    'provider': 'claude',
                    'model': config['model']
                }
            else:
                error_msg = response.json().get('error', {}).get('message', '未知错误')
                return {'success': False, 'message': f'Claude API错误: {error_msg}'}
                
        except requests.RequestException as e:
            return {'success': False, 'message': f'Claude API调用失败: {str(e)}'}
    
    def _call_ollama_api(self, prompt: str) -> Dict:
        """调用Ollama API"""
        config = self.api_configs['ollama']
        
        data = {
            'model': config['model'],
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': config.get('temperature', 0.7)
            }
        }
        
        try:
            response = requests.post(
                f"{config['base_url']}/api/generate",
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('response', '')
                
                # 添加到对话历史
                self.conversation_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'provider': 'ollama',
                    'user_input': prompt,
                    'ai_response': content
                })
                
                return {
                    'success': True,
                    'response': content,
                    'provider': 'ollama',
                    'model': config['model']
                }
            else:
                return {'success': False, 'message': f'Ollama API错误: {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'message': f'Ollama API调用失败: {str(e)}'}
    
    def _call_deepseek_api(self, prompt: str) -> Dict:
        """调用DeepSeek API"""
        config = self.api_configs['deepseek']
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {config['api_key']}"
        }
        
        data = {
            'model': config['model'],
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': config['max_tokens'],
            'temperature': 0.7
        }
        
        try:
            response = requests.post(
                f"{config['base_url']}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 添加到对话历史
                self.conversation_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'provider': 'deepseek',
                    'user_input': prompt,
                    'ai_response': content
                })
                
                return {
                    'success': True,
                    'response': content,
                    'provider': 'deepseek',
                    'model': config['model']
                }
            else:
                error_msg = response.json().get('error', {}).get('message', '未知错误')
                return {'success': False, 'message': f'DeepSeek API错误: {error_msg}'}
                
        except requests.RequestException as e:
            return {'success': False, 'message': f'DeepSeek API调用失败: {str(e)}'}
    
    def chat(self, provider: str, user_message: str, context: Dict = None) -> Dict:
        """简单对话功能"""
        try:
            # 如果有上下文信息，添加到消息中
            if context:
                enhanced_message = f"""
用户消息: {user_message}

当前期权搜索上下文:
- 基础币种: {context.get('base_coin', 'BTC')}
- 期权方向: {context.get('direction', 'Call')}
- 目标价格: ${context.get('target_price', 0):,.0f}
- 目标天数: {context.get('days', 0)}天

请基于这个上下文回答用户的问题。
"""
            else:
                enhanced_message = user_message
            
            # 根据提供商调用相应的API
            if provider == 'claude':
                return self._call_claude_api(enhanced_message)
            elif provider == 'ollama':
                return self._call_ollama_api(enhanced_message)
            elif provider == 'deepseek':
                return self._call_deepseek_api(enhanced_message)
            else:
                return {'success': False, 'message': '不支持的AI服务提供商'}
                
        except Exception as e:
            return {'success': False, 'message': f'对话失败: {str(e)}'}
    
    def get_conversation_history(self) -> List[Dict]:
        """获取对话历史"""
        return self.conversation_history
    
    def clear_conversation_history(self):
        """清除对话历史"""
        self.conversation_history = []
    
    def generate_trading_tasks(self, analysis_result: str, user_preferences: Dict = None) -> List[Dict]:
        """根据分析结果生成交易任务清单"""
        tasks = []
        
        # 基于AI分析结果提取任务（这里是简化版本，实际可以用NLP进一步解析）
        if '买入' in analysis_result or '购买' in analysis_result:
            tasks.append({
                'id': f"task_{int(time.time())}",
                'type': 'buy_option',
                'title': '买入推荐期权',
                'description': '根据AI分析买入推荐的期权合约',
                'priority': 'high',
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            })
        
        if '卖出' in analysis_result:
            tasks.append({
                'id': f"task_{int(time.time())}_1",
                'type': 'sell_option',
                'title': '卖出期权',
                'description': '根据AI分析卖出指定期权合约',
                'priority': 'medium',
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            })
        
        if '监控' in analysis_result or '观察' in analysis_result:
            tasks.append({
                'id': f"task_{int(time.time())}_2",
                'type': 'monitor',
                'title': '市场监控',
                'description': '监控推荐期权的价格变化',
                'priority': 'low',
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            })
        
        return tasks

# 创建全局AI助手实例
ai_assistant = AIAssistant()

