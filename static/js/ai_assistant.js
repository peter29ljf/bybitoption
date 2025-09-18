// AI助手前端JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // AI相关DOM元素
    const aiProvider = document.getElementById('aiProvider');
    const aiApiKey = document.getElementById('aiApiKey');
    const toggleApiKey = document.getElementById('toggleApiKey');
    const testConnection = document.getElementById('testConnection');
    const saveConfig = document.getElementById('saveConfig');
    const aiConnectionStatus = document.getElementById('aiConnectionStatus');
    const aiStatusText = document.getElementById('aiStatusText');
    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendMessage = document.getElementById('sendMessage');
    const analyzeOptions = document.getElementById('analyzeOptions');
    const clearChat = document.getElementById('clearChat');
    const aiTasks = document.getElementById('aiTasks');

    // 当前AI服务状态
    let currentProvider = 'claude';
    let isConnected = false;

    // 初始化AI助手
    initAIAssistant();

    function initAIAssistant() {
        // 绑定事件监听器
        bindAIEventListeners();
        
        // 加载配置
        loadAIConfig();
    }

    function bindAIEventListeners() {
        // AI服务提供商改变
        aiProvider.addEventListener('change', function() {
            currentProvider = this.value;
            loadAIConfig();
            updateUIState();
        });

        // 切换API密钥显示/隐藏
        toggleApiKey.addEventListener('click', function() {
            const type = aiApiKey.type === 'password' ? 'text' : 'password';
            aiApiKey.type = type;
            this.innerHTML = type === 'password' ? '<i class="bi bi-eye"></i>' : '<i class="bi bi-eye-slash"></i>';
        });

        // 测试连接
        testConnection.addEventListener('click', testAIConnection);

        // 保存配置
        saveConfig.addEventListener('click', saveAIConfig);

        // 发送消息
        sendMessage.addEventListener('click', sendChatMessage);
        
        // 回车发送消息
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });

        // 分析期权
        analyzeOptions.addEventListener('click', analyzeCurrentOptions);

        // 清除对话历史
        clearChat.addEventListener('click', clearChatHistory);
    }

    async function loadAIConfig() {
        try {
            const response = await fetch(`/ai/config/${currentProvider}`);
            const result = await response.json();
            
            if (result.success) {
                const config = result.config;
                
                // 根据不同服务更新UI
                if (currentProvider === 'ollama') {
                    aiApiKey.parentElement.parentElement.style.display = 'none';
                } else {
                    aiApiKey.parentElement.parentElement.style.display = 'block';
                    aiApiKey.value = config.api_key || '';
                }
                
                updateConnectionStatus('info', '配置已加载，请测试连接');
            }
        } catch (error) {
            console.error('加载AI配置失败:', error);
            updateConnectionStatus('danger', '加载配置失败');
        }
    }

    async function testAIConnection() {
        testConnection.disabled = true;
        testConnection.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> 测试中...';
        
        try {
            const response = await fetch(`/ai/test/${currentProvider}`);
            const result = await response.json();
            
            if (result.success) {
                isConnected = true;
                updateConnectionStatus('success', result.message);
                updateUIState();
            } else {
                isConnected = false;
                updateConnectionStatus('danger', result.message);
                updateUIState();
            }
        } catch (error) {
            console.error('测试连接失败:', error);
            isConnected = false;
            updateConnectionStatus('danger', '网络错误，测试失败');
            updateUIState();
        } finally {
            testConnection.disabled = false;
            testConnection.innerHTML = '<i class="bi bi-plug"></i> 测试';
        }
    }

    async function saveAIConfig() {
        saveConfig.disabled = true;
        saveConfig.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> 保存中...';
        
        try {
            const configData = {};
            
            if (currentProvider !== 'ollama') {
                configData.api_key = aiApiKey.value.trim();
                
                if (!configData.api_key) {
                    updateConnectionStatus('warning', '请输入API密钥');
                    return;
                }
            }
            
            const response = await fetch(`/ai/config/${currentProvider}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(configData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                updateConnectionStatus('success', result.message);
                // 自动测试连接
                setTimeout(() => {
                    testAIConnection();
                }, 500);
            } else {
                updateConnectionStatus('danger', result.message);
            }
        } catch (error) {
            console.error('保存配置失败:', error);
            updateConnectionStatus('danger', '保存配置失败');
        } finally {
            saveConfig.disabled = false;
            saveConfig.innerHTML = '<i class="bi bi-check"></i> 保存';
        }
    }

    function updateConnectionStatus(type, message) {
        aiConnectionStatus.className = `alert alert-${type}`;
        aiConnectionStatus.classList.remove('d-none');
        aiStatusText.textContent = message;
    }

    function updateUIState() {
        // 根据连接状态启用/禁用聊天功能
        chatInput.disabled = !isConnected;
        sendMessage.disabled = !isConnected;
        analyzeOptions.disabled = !isConnected;
        
        if (isConnected) {
            chatInput.placeholder = '输入您的问题...';
        } else {
            chatInput.placeholder = '请先配置并测试AI服务连接';
        }
    }

    async function sendChatMessage() {
        const message = chatInput.value.trim();
        if (!message || !isConnected) return;
        
        // 清空输入框
        chatInput.value = '';
        
        // 显示用户消息
        addChatMessage('user', message);
        
        // 显示AI思考状态
        const thinkingId = addChatMessage('ai', '正在思考...', true);
        
        try {
            // 获取当前搜索上下文
            const context = getCurrentSearchContext();
            
            const response = await fetch(`/ai/chat/${currentProvider}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    context: context
                })
            });
            
            const result = await response.json();
            
            // 移除思考状态
            document.getElementById(thinkingId).remove();
            
            if (result.success) {
                addChatMessage('ai', result.response);
            } else {
                addChatMessage('ai', `错误: ${result.message}`, false, 'error');
            }
        } catch (error) {
            console.error('发送消息失败:', error);
            document.getElementById(thinkingId).remove();
            addChatMessage('ai', '网络错误，请稍后重试', false, 'error');
        }
    }

    async function analyzeCurrentOptions() {
        if (!isConnected) {
            showToast('请先配置AI服务', 'warning');
            return;
        }
        
        // 获取当前搜索参数
        const searchParams = getCurrentSearchParams();
        
        if (!searchParams.target_price || !searchParams.days) {
            showToast('请先进行期权搜索', 'warning');
            return;
        }
        
        // 添加分析请求消息
        addChatMessage('user', '请分析当前搜索的期权数据并给出交易建议');
        
        // 显示分析状态
        const analysisId = addChatMessage('ai', '正在分析期权数据，请稍候...', true);
        
        try {
            const response = await fetch(`/ai/analyze/${currentProvider}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: '请分析这些期权数据并给出详细的交易建议',
                    search_params: searchParams
                })
            });
            
            const result = await response.json();
            
            // 移除分析状态
            document.getElementById(analysisId).remove();
            
            if (result.success) {
                addChatMessage('ai', result.response);
                
                // 显示任务清单
                if (result.tasks && result.tasks.length > 0) {
                    displayTasks(result.tasks);
                }
                
                showToast('期权分析完成', 'success');
            } else {
                addChatMessage('ai', `分析失败: ${result.message}`, false, 'error');
                showToast('分析失败', 'error');
            }
        } catch (error) {
            console.error('分析失败:', error);
            document.getElementById(analysisId).remove();
            addChatMessage('ai', '分析过程中发生错误，请稍后重试', false, 'error');
            showToast('网络错误', 'error');
        }
    }

    function addChatMessage(sender, content, isTemporary = false, type = 'normal') {
        const messageId = 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        const isUser = sender === 'user';
        
        let messageClass = isUser ? 'text-end' : '';
        let badgeClass = isUser ? 'bg-primary' : 'bg-secondary';
        let contentClass = 'p-3 rounded-3 d-inline-block';
        
        if (type === 'error') {
            badgeClass = 'bg-danger';
        } else if (isTemporary) {
            badgeClass = 'bg-info';
        }
        
        if (isUser) {
            contentClass += ' bg-primary text-white ms-auto';
        } else {
            contentClass += ' bg-light';
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.id = messageId;
        messageDiv.className = `mb-3 ${messageClass}`;
        messageDiv.innerHTML = `
            <div class="${contentClass}" style="max-width: 80%;">
                <div class="d-flex align-items-center mb-2">
                    <span class="badge ${badgeClass} me-2">
                        <i class="bi bi-${isUser ? 'person' : 'robot'}"></i>
                        ${isUser ? '您' : 'AI'}
                    </span>
                    <small class="text-muted">${new Date().toLocaleTimeString()}</small>
                </div>
                <div class="message-content">${formatMessageContent(content)}</div>
            </div>
        `;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return messageId;
    }

    function formatMessageContent(content) {
        // 简单的markdown-like格式化
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>')
            .replace(/```(.*?)```/gs, '<pre class="bg-dark text-light p-2 rounded mt-2">$1</pre>');
    }

    async function clearChatHistory() {
        if (confirm('确定要清除所有对话历史吗？')) {
            try {
                const response = await fetch('/ai/clear_history', {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    chatMessages.innerHTML = `
                        <div class="text-center text-muted">
                            <i class="bi bi-robot"></i>
                            <p>对话历史已清除</p>
                        </div>
                    `;
                    showToast('对话历史已清除', 'success');
                } else {
                    showToast('清除失败', 'error');
                }
            } catch (error) {
                console.error('清除历史失败:', error);
                showToast('清除失败', 'error');
            }
        }
    }

    function displayTasks(tasks) {
        if (tasks.length === 0) {
            aiTasks.innerHTML = `
                <div class="text-center text-muted">
                    <i class="bi bi-clipboard"></i>
                    <p>暂无推荐任务</p>
                </div>
            `;
            return;
        }
        
        let tasksHtml = '';
        
        tasks.forEach(task => {
            const priorityClass = {
                'high': 'danger',
                'medium': 'warning',
                'low': 'info'
            }[task.priority] || 'secondary';
            
            const typeIcon = {
                'buy_option': 'cart-plus',
                'sell_option': 'cart-dash',
                'monitor': 'eye'
            }[task.type] || 'check-circle';
            
            tasksHtml += `
                <div class="card mb-2">
                    <div class="card-body p-3">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h6 class="card-title mb-1">
                                    <i class="bi bi-${typeIcon}"></i>
                                    ${task.title}
                                </h6>
                                <p class="card-text text-muted small mb-2">${task.description}</p>
                                <small class="text-muted">创建时间: ${new Date(task.created_at).toLocaleString()}</small>
                            </div>
                            <div class="ms-3">
                                <span class="badge bg-${priorityClass}">${task.priority}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        aiTasks.innerHTML = tasksHtml;
    }

    function getCurrentSearchParams() {
        return {
            base_coin: document.getElementById('baseCoin')?.value || 'BTC',
            direction: document.getElementById('direction')?.value || 'Call',
            target_price: document.getElementById('targetPrice')?.value || '',
            days: document.getElementById('days')?.value || ''
        };
    }

    function getCurrentSearchContext() {
        const params = getCurrentSearchParams();
        return {
            base_coin: params.base_coin,
            direction: params.direction,
            target_price: parseFloat(params.target_price) || 0,
            days: parseInt(params.days) || 0
        };
    }

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = '9999';
        
        const bgClass = {
            'success': 'bg-success',
            'error': 'bg-danger',
            'warning': 'bg-warning',
            'info': 'bg-info'
        }[type] || 'bg-info';
        
        toast.innerHTML = `
            <div class="toast show ${bgClass} text-white" role="alert">
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    // 导出函数供全局使用
    window.aiAssistant = {
        analyzeCurrentOptions,
        getCurrentSearchParams,
        showToast
    };
});

