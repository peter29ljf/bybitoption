// Strategy management frontend logic

document.addEventListener('DOMContentLoaded', () => {
    const strategyTable = document.getElementById('strategyTable');
    if (!strategyTable) {
        return;
    }

    const strategyTableWrapper = document.getElementById('strategyTableWrapper');
    const strategyEmpty = document.getElementById('strategyEmpty');
    const strategyDetailCard = document.getElementById('strategyDetailCard');
    const strategyDetailTitle = document.getElementById('strategyDetailTitle');
    const strategyDetailDescription = document.getElementById('strategyDetailDescription');
    const levelStatusTable = document.querySelector('#levelStatusTable tbody');
    const createStrategyBtn = document.getElementById('createStrategyBtn');
    const editStrategyBtn = document.getElementById('editStrategyBtn');
    const pauseStrategyBtn = document.getElementById('pauseStrategyBtn');
    const deleteStrategyBtn = document.getElementById('deleteStrategyBtn');
    const refreshTradesBtn = document.getElementById('refreshTradesBtn');
    const tradeLogTable = document.getElementById('tradeLogTable');

    const strategyModal = new bootstrap.Modal(document.getElementById('strategyModal'));
    const strategyForm = document.getElementById('strategyForm');
    const strategyIdInput = document.getElementById('strategyId');
    const strategyNameInput = document.getElementById('strategyName');
    const strategyDescriptionInput = document.getElementById('strategyDescription');
    const addLevelBtn = document.getElementById('addLevelBtn');
    const levelsContainer = document.getElementById('levelsContainer');
    const saveStrategyBtn = document.getElementById('saveStrategyBtn');
    const levelTemplate = document.getElementById('levelTemplate');

    let watchlistOptions = [];
    let strategies = [];
    let currentStrategy = null;

    const generateLevelId = () => {
        if (window.crypto && window.crypto.randomUUID) {
            return `lvl-${window.crypto.randomUUID()}`;
        }
        return `lvl-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    };

    init();

    function init() {
        loadWatchlist();
        loadStrategies();
        loadTrades();
        bindEvents();
    }

    function bindEvents() {
        createStrategyBtn.addEventListener('click', () => openStrategyModal());
        saveStrategyBtn.addEventListener('click', handleSaveStrategy);
        addLevelBtn.addEventListener('click', addLevelForm);
        editStrategyBtn.addEventListener('click', () => {
            if (currentStrategy) {
                openStrategyModal(currentStrategy);
            }
        });
        pauseStrategyBtn.addEventListener('click', handlePauseResumeStrategy);
        deleteStrategyBtn.addEventListener('click', handleDeleteStrategy);
        refreshTradesBtn.addEventListener('click', loadTrades);
    }

    async function loadWatchlist() {
        try {
            const response = await fetch('/watchlist');
            const result = await response.json();
            if (result.success) {
                watchlistOptions = result.watchlist || [];
            }
        } catch (error) {
            console.error('加载关注列表失败:', error);
        }
    }

    async function loadStrategies() {
        try {
            const response = await fetch('/api/strategies');
            const result = await response.json();
            if (result.success) {
                strategies = result.strategies || [];
                renderStrategyTable();
            }
        } catch (error) {
            console.error('加载策略失败:', error);
        }
    }

    function renderStrategyTable() {
        strategyTable.innerHTML = '';
        if (strategies.length === 0) {
            strategyEmpty.classList.remove('d-none');
            strategyTableWrapper.classList.add('d-none');
            strategyDetailCard.classList.add('d-none');
            currentStrategy = null;
            return;
        }

        strategyEmpty.classList.add('d-none');
        strategyTableWrapper.classList.remove('d-none');

        strategies.forEach((strategy) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${strategy.name}</td>
                <td>${renderStatusBadge(strategy.status)}</td>
                <td>${strategy.levels ? strategy.levels.length : 0}</td>
                <td>${strategy.updated_at || strategy.created_at}</td>
                <td>
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-secondary" data-action="view">查看</button>
                        <button class="btn btn-outline-primary" data-action="edit">编辑</button>
                        <button class="btn btn-outline-danger" data-action="delete">删除</button>
                    </div>
                </td>
            `;

            row.querySelector('[data-action="view"]').addEventListener('click', () => showStrategyDetail(strategy.strategy_id));
            row.querySelector('[data-action="edit"]').addEventListener('click', () => openStrategyModal(strategy));
            row.querySelector('[data-action="delete"]').addEventListener('click', () => confirmDeleteStrategy(strategy));

            strategyTable.appendChild(row);
        });

        // Show first strategy detail by default
        showStrategyDetail(strategies[0].strategy_id);
    }

    function renderStatusBadge(status) {
        const map = {
            running: 'success',
            paused: 'warning',
            stopped: 'secondary'
        };
        const textMap = {
            running: '运行中',
            paused: '已暂停',
            stopped: '已停止'
        };
        const color = map[status] || 'secondary';
        const text = textMap[status] || status;
        return `<span class="badge bg-${color}">${text}</span>`;
    }

    function showStrategyDetail(strategyId) {
        currentStrategy = strategies.find((item) => item.strategy_id === strategyId);
        if (!currentStrategy) {
            strategyDetailCard.classList.add('d-none');
            return;
        }

        strategyDetailCard.classList.remove('d-none');
        strategyDetailTitle.textContent = currentStrategy.name;
        strategyDetailDescription.textContent = currentStrategy.description || '';

        pauseStrategyBtn.textContent = currentStrategy.status === 'running' ? '暂停' : '恢复';
        pauseStrategyBtn.classList.toggle('btn-outline-warning', currentStrategy.status === 'running');
        pauseStrategyBtn.classList.toggle('btn-outline-success', currentStrategy.status !== 'running');

        levelStatusTable.innerHTML = '';
        (currentStrategy.levels || []).forEach((level) => {
            const row = document.createElement('tr');
            const monitorBadges = Object.entries(level.monitor_task_ids || {}).map(([type, taskId]) => {
                return `<span class="badge bg-info text-dark me-1">${type}: ${taskId}</span>`;
            }).join('');

            row.innerHTML = `
                <td><code>${level.level_id}</code></td>
                <td>${level.option_symbol}</td>
                <td>${level.side === 'buy' ? '买入' : '卖出'}</td>
                <td>${formatTriggerDescription(level)}</td>
                <td>${renderLevelStatus(level.status)}</td>
                <td>${monitorBadges || '-'}</td>
                <td>${level.last_update || '-'}</td>
            `;
            levelStatusTable.appendChild(row);
        });
    }

    function formatTriggerDescription(level) {
        if (level.trigger_type === 'immediate') {
            return '立即执行';
        }
        if (level.trigger_type === 'conditional') {
            const price = level.trigger_price ? level.trigger_price : '-';
            return `条件 (${price})`;
        }
        if (level.trigger_type === 'existing_position') {
            return '使用现有仓位';
        }
        if (level.trigger_type === 'level_close') {
            const target = level.trigger_level_id ? level.trigger_level_id : '未选择';
            const eventMap = { TAKE_PROFIT: '止盈', STOP_LOSS: '止损' };
            const event = level.trigger_level_event ? (eventMap[level.trigger_level_event] || level.trigger_level_event) : '任意';
            return `Level平仓 (${target} / ${event})`;
        }
        return level.trigger_type || '-';
    }

    function renderLevelStatus(status) {
        const map = {
            pending: 'secondary',
            waiting: 'warning',
            monitoring: 'info',
            executing: 'primary',
            completed: 'success',
            failed: 'danger',
            cancelled: 'secondary'
        };
        const textMap = {
            pending: '待执行',
            waiting: '等待触发',
            monitoring: '监控中',
            executing: '执行中',
            completed: '已完成',
            failed: '失败',
            cancelled: '已取消'
        };
        const color = map[status] || 'secondary';
        const text = textMap[status] || status;
        return `<span class="badge bg-${color}">${text}</span>`;
    }

    async function openStrategyModal(strategy = null) {
        await loadWatchlist();
        strategyForm.reset();
        levelsContainer.innerHTML = '';
        strategyIdInput.value = strategy ? strategy.strategy_id : '';
        strategyNameInput.value = strategy ? strategy.name : '';
        strategyDescriptionInput.value = strategy ? (strategy.description || '') : '';

        if (strategy && strategy.levels) {
            strategy.levels.forEach((level) => addLevelForm(level));
        } else {
            addLevelForm();
        }

        refreshLevelIndexes();
        strategyModal.show();
    }

    function addLevelForm(level = null) {
        const fragment = levelTemplate.content.cloneNode(true);
        const wrapper = fragment.querySelector('.level-item');
        const symbolSelect = fragment.querySelector('.level-symbol');
        const triggerTypeSelect = fragment.querySelector('.level-trigger-type');
        const triggerPriceGroup = fragment.querySelector('.conditional-field');
        const linkedFields = fragment.querySelectorAll('.linked-field');
        const linkedLevelSelect = fragment.querySelector('.level-linked-level');
        const linkedEventSelect = fragment.querySelector('.level-linked-event');

        const currentLevelId = level && level.level_id ? level.level_id : generateLevelId();
        wrapper.dataset.levelId = currentLevelId;

        populateSymbolOptions(symbolSelect, level ? level.option_symbol : null);
        fragment.querySelector('.level-side').value = level ? level.side : 'buy';
        fragment.querySelector('.level-quantity').value = level ? level.quantity : '1';
        triggerTypeSelect.value = level ? level.trigger_type : 'immediate';
        fragment.querySelector('.level-trigger-price').value = level && level.trigger_price ? level.trigger_price : '';
        fragment.querySelector('.level-take-profit').value = level && level.take_profit ? level.take_profit : '';
        fragment.querySelector('.level-stop-loss').value = level && level.stop_loss ? level.stop_loss : '';
        linkedEventSelect.value = level && level.trigger_level_event ? level.trigger_level_event : 'ANY';

        populateLinkedLevelOptions(linkedLevelSelect, currentLevelId, level ? level.trigger_level_id : null);

        const toggleTriggerFields = () => {
            if (triggerTypeSelect.value === 'conditional') {
                triggerPriceGroup.classList.remove('d-none');
            } else {
                triggerPriceGroup.classList.add('d-none');
            }

            if (triggerTypeSelect.value === 'level_close') {
                linkedFields.forEach((field) => field.classList.remove('d-none'));
                populateLinkedLevelOptions(linkedLevelSelect, currentLevelId);
            } else {
                linkedFields.forEach((field) => field.classList.add('d-none'));
            }
        };

        triggerTypeSelect.addEventListener('change', () => {
            toggleTriggerFields();
        });

        fragment.querySelector('.remove-level-btn').addEventListener('click', () => {
            wrapper.remove();
            if (!levelsContainer.querySelector('.level-item')) {
                addLevelForm();
            }
            refreshLevelIndexes();
            refreshLinkedOptions();
        });

        levelsContainer.appendChild(fragment);
        refreshLevelIndexes();
        refreshLinkedOptions();
        toggleTriggerFields();
    }

    function populateSymbolOptions(select, selectedSymbol) {
        select.innerHTML = '';
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '选择期权...';
        select.appendChild(defaultOption);

        watchlistOptions.forEach((item) => {
            const option = document.createElement('option');
            option.value = item.symbol;
            option.textContent = `${item.symbol} (${item.base_coin || ''})`;
            if (item.symbol === selectedSymbol) {
                option.selected = true;
            }
            select.appendChild(option);
        });
    }

    function getLevelOptions(excludeId = null) {
        return Array.from(levelsContainer.querySelectorAll('.level-item')).map((item, index) => {
            const id = item.dataset.levelId;
            const symbol = item.querySelector('.level-symbol').value;
            const label = symbol ? `${symbol}` : `Level ${index + 1}`;
            return { id, label, index: index + 1 };
        }).filter((entry) => entry.id && entry.id !== excludeId);
    }

    function populateLinkedLevelOptions(select, excludeId, selectedId = null) {
        if (!select) return;
        const previous = selectedId !== null ? selectedId : select.value;
        select.innerHTML = '';
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = '选择依赖Level...';
        select.appendChild(placeholder);

        let matched = false;
        getLevelOptions(excludeId).forEach((entry) => {
            const option = document.createElement('option');
            option.value = entry.id;
            option.textContent = `Level ${entry.index} - ${entry.label}`;
            if (entry.id === previous) {
                option.selected = true;
                matched = true;
            }
            select.appendChild(option);
        });

        if (previous && !matched) {
            const fallback = document.createElement('option');
            fallback.value = previous;
            fallback.textContent = `${previous} (已不存在)`;
            fallback.selected = true;
            select.appendChild(fallback);
        }
    }

    function refreshLinkedOptions() {
        const items = levelsContainer.querySelectorAll('.level-item');
        items.forEach((item) => {
            const select = item.querySelector('.level-linked-level');
            if (!select) return;
            const currentId = item.dataset.levelId;
            const selectedValue = select.value;
            populateLinkedLevelOptions(select, currentId, selectedValue);
        });
    }

    async function handleSaveStrategy() {
        if (!strategyForm.reportValidity()) {
            return;
        }

        const collected = collectLevelData();
        if (!collected.valid) {
            return;
        }

        const payload = {
            name: strategyNameInput.value.trim(),
            description: strategyDescriptionInput.value.trim(),
            levels: collected.levels
        };

        if (!payload.levels.length) {
            showErrorToast('保存策略失败', '请至少配置一个有效的Level');
            return;
        }

        const strategyId = strategyIdInput.value;
        const method = strategyId ? 'PUT' : 'POST';
        const url = strategyId ? `/api/strategies/${strategyId}` : '/api/strategies';

        try {
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (result.success) {
                strategyModal.hide();
                await loadStrategies();
                showStrategyDetail(result.strategy.strategy_id);
            } else {
                showErrorToast('保存策略失败', result.message || '请稍后重试');
            }
        } catch (error) {
            console.error('保存策略失败:', error);
            showErrorToast('保存策略失败', '网络错误');
        }
    }

    function collectLevelData() {
        const levels = [];
        let valid = true;
        const levelItems = levelsContainer.querySelectorAll('.level-item');
        levelItems.forEach((item, index) => {
            const levelId = item.dataset.levelId || null;
            const symbol = item.querySelector('.level-symbol').value;
            if (!symbol) {
                return;
            }
            const triggerType = item.querySelector('.level-trigger-type').value;
            const triggerPriceInput = item.querySelector('.level-trigger-price');
            const takeProfitInput = item.querySelector('.level-take-profit');
            const stopLossInput = item.querySelector('.level-stop-loss');
            const linkedLevelSelect = item.querySelector('.level-linked-level');
            const linkedEventSelect = item.querySelector('.level-linked-event');

            const levelPayload = {
                level_id: levelId,
                option_symbol: symbol,
                side: item.querySelector('.level-side').value,
                quantity: item.querySelector('.level-quantity').value,
                trigger_type: triggerType,
                trigger_price: triggerType === 'conditional' ? parseFloat(triggerPriceInput.value || '0') || null : null,
                take_profit: takeProfitInput.value ? parseFloat(takeProfitInput.value) : null,
                stop_loss: stopLossInput.value ? parseFloat(stopLossInput.value) : null,
                trigger_level_id: triggerType === 'level_close' ? (linkedLevelSelect ? linkedLevelSelect.value : null) || null : null,
                trigger_level_event: triggerType === 'level_close' ? (linkedEventSelect && linkedEventSelect.value === 'ANY' ? null : linkedEventSelect.value) : null
            };

            if (triggerType === 'level_close' && !levelPayload.trigger_level_id) {
                showErrorToast('保存策略失败', `Level ${index + 1} 请选择依赖的触发Level`);
                valid = false;
                return;
            }
            levels.push(levelPayload);
        });
        return { levels, valid };
    }

    async function handlePauseResumeStrategy() {
        if (!currentStrategy) {
            return;
        }
        const action = currentStrategy.status === 'running' ? 'pause' : 'resume';
        try {
            const response = await fetch(`/api/strategies/${currentStrategy.strategy_id}/${action}`, { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                await loadStrategies();
                showStrategyDetail(result.strategy.strategy_id);
            }
        } catch (error) {
            console.error('更新策略状态失败:', error);
        }
    }

    async function handleDeleteStrategy() {
        if (!currentStrategy) {
            return;
        }
        confirmDeleteStrategy(currentStrategy);
    }

    function confirmDeleteStrategy(strategy) {
        if (!window.confirm(`确定要删除策略 ${strategy.name} 吗？`)) {
            return;
        }
        fetch(`/api/strategies/${strategy.strategy_id}`, { method: 'DELETE' })
            .then((response) => response.json())
            .then((result) => {
                if (result.success) {
                    loadStrategies();
                }
            })
            .catch((error) => console.error('删除策略失败:', error));
    }

    function refreshLevelIndexes() {
        const levelItems = levelsContainer.querySelectorAll('.level-item');
        levelItems.forEach((item, index) => {
            const label = item.querySelector('.level-index');
            if (label) {
                label.textContent = index + 1;
            }
        });
        refreshLinkedOptions();
    }

    async function loadTrades() {
        try {
            const response = await fetch('/api/strategies/trades?limit=200');
            const result = await response.json();
            if (result.success) {
                renderTrades(result.trades || []);
            }
        } catch (error) {
            console.error('加载交易记录失败:', error);
        }
    }

    function renderTrades(trades) {
        tradeLogTable.innerHTML = '';
        if (!trades.length) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="11" class="text-center text-muted">暂无交易记录</td>';
            tradeLogTable.appendChild(row);
            return;
        }

        trades.forEach((trade) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${trade.created_at || '-'}</td>
                <td>${trade.strategy_id || '-'}</td>
                <td>${trade.level_id || '-'}</td>
                <td>${trade.monitor_type || '-'}</td>
                <td>${trade.option_symbol || '-'}</td>
                <td>${trade.side === 'buy' ? '买入' : '卖出'}</td>
                <td>${trade.quantity || '-'}</td>
                <td>${formatNumber(trade.trigger_price)}</td>
                <td>${formatNumber(trade.target_price)}</td>
                <td>${trade.success ? '<span class="badge bg-success">成功</span>' : '<span class="badge bg-danger">失败</span>'}</td>
                <td>${trade.message || '-'}</td>
            `;
            tradeLogTable.appendChild(row);
        });
    }

    function formatNumber(value) {
        if (value === null || value === undefined || value === '') {
            return '-';
        }
        const numeric = Number(value);
        if (Number.isNaN(numeric)) {
            return value;
        }
        return numeric.toFixed(4);
    }

    function showErrorToast(title, message) {
        const toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="toast show bg-danger text-white" role="alert">
                <div class="toast-header bg-danger text-white border-0">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    <strong class="me-auto">${title}</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">${message}</div>
            </div>
        `;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }
});
