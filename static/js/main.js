// Bybit期权链搜索工具JavaScript文件

document.addEventListener('DOMContentLoaded', function() {
    // 获取DOM元素
    const searchForm = document.getElementById('searchForm');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const searchResults = document.getElementById('searchResults');
    const errorMessage = document.getElementById('errorMessage');
    const loadStrikePricesBtn = document.getElementById('loadStrikePrices');
    const getExpiryDatesBtn = document.getElementById('getExpiryDates');
    const baseCoinSelect = document.getElementById('baseCoin');
    const targetPriceSelect = document.getElementById('targetPrice');
    const currentPriceSpan = document.getElementById('currentPrice');
    const refreshDataBtn = document.getElementById('refreshDataBtn');
    const dataStatusBar = document.getElementById('dataStatusBar');
    const dataStatusText = document.getElementById('dataStatusText');
    const dataStatusDetails = document.getElementById('dataStatusDetails');
    const watchlistSection = document.getElementById('watchlistSection');
    const watchlistCount = document.getElementById('watchlistCount');
    const watchlistTable = document.getElementById('watchlistTable');
    const watchlistTableWrapper = document.getElementById('watchlistTableWrapper');
    const watchlistEmpty = document.getElementById('watchlistEmpty');
    const clearWatchlistBtn = document.getElementById('clearWatchlistBtn');

    const watchlistState = {
        symbols: new Set(),
        items: []
    };

    // 初始化
    init();

    function init() {
        // 检查数据状态
        checkDataStatus();
        
        // 获取当前价格
        updateCurrentPrice();
        
        // 绑定事件监听器
        bindEventListeners();
        
        // 设置默认值
        setDefaultValues();

        // 加载关注列表
        loadWatchlist();
    }

    function bindEventListeners() {
        // 搜索表单提交
        searchForm.addEventListener('submit', handleSearch);
        
        // 加载执行价格按钮
        loadStrikePricesBtn.addEventListener('click', loadStrikePrices);
        
        // 查看可用日期按钮
        getExpiryDatesBtn.addEventListener('click', showExpiryDates);
        
        // 刷新数据按钮
        refreshDataBtn.addEventListener('click', refreshData);
        
        // 基础币种改变时更新价格和执行价格
        baseCoinSelect.addEventListener('change', function() {
            updateCurrentPrice();
            checkDataStatus();
        });

        if (clearWatchlistBtn) {
            clearWatchlistBtn.addEventListener('click', handleClearWatchlist);
        }
    }

    function setDefaultValues() {
        // 设置默认天数
        const daysInput = document.getElementById('days');
        if (!daysInput.value) {
            daysInput.value = 7; // 默认7天
        }
    }

    const formatPrice = (price, decimals = 4) => {
        if (price === null || price === undefined) return '-';
        const numeric = Number(price);
        if (Number.isNaN(numeric) || numeric <= 0) return '-';
        return `$${numeric.toFixed(decimals)}`;
    };

    const formatVolume = (volume) => {
        if (volume === null || volume === undefined) return '-';
        const numeric = Number(volume);
        if (Number.isNaN(numeric) || numeric <= 0) return '-';
        return numeric.toLocaleString();
    };

    const formatPercent = (value, decimals = 2) => {
        if (value === null || value === undefined) return '-';
        const numeric = Number(value);
        if (Number.isNaN(numeric)) return '-';
        return `${numeric.toFixed(decimals)}%`;
    };

    const formatGreek = (value, decimals = 6) => {
        if (value === null || value === undefined) return '-';
        const numeric = Number(value);
        if (Number.isNaN(numeric)) return '-';
        return numeric.toFixed(decimals);
    };

    const formatAddedAt = (timestamp) => {
        if (!timestamp) {
            return '-';
        }
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) {
            return '-';
        }
        return date.toLocaleString();
    };

    async function loadWatchlist() {
        try {
            const response = await fetch('/watchlist');
            const result = await response.json();

            if (result.success) {
                updateWatchlistDisplay(result.watchlist || []);
            } else {
                showErrorToast('加载关注列表失败', result.message || '请稍后再试');
            }
        } catch (error) {
            console.error('加载关注列表错误:', error);
            showErrorToast('加载关注列表失败', '网络错误，请稍后重试');
        }
    }

    function updateWatchlistDisplay(items) {
        if (!watchlistSection) {
            return;
        }

        watchlistSection.classList.remove('d-none');

        watchlistState.items = items;
        watchlistState.symbols = new Set(items.map(item => item.symbol));

        const count = items.length;
        if (watchlistCount) {
            watchlistCount.textContent = `${count} 个关注`;
        }

        if (clearWatchlistBtn) {
            clearWatchlistBtn.disabled = count === 0;
        }

        if (count === 0) {
            if (watchlistEmpty) {
                watchlistEmpty.classList.remove('d-none');
            }
            if (watchlistTableWrapper) {
                watchlistTableWrapper.classList.add('d-none');
            }
            if (watchlistTable) {
                watchlistTable.innerHTML = '';
            }
        } else {
            if (watchlistEmpty) {
                watchlistEmpty.classList.add('d-none');
            }
            if (watchlistTableWrapper) {
                watchlistTableWrapper.classList.remove('d-none');
            }
            renderWatchlistTable(items);
        }

        refreshWatchButtons();
    }

    function renderWatchlistTable(items) {
        if (!watchlistTable) {
            return;
        }

        watchlistTable.innerHTML = '';

        items.forEach(item => {
            const row = document.createElement('tr');
            const strikePrice = item.strike_price ? `$${Number(item.strike_price).toLocaleString()}` : '-';
            const expiryLabel = item.expiry_date_formatted || '-';
            const daysLabel = Number.isFinite(item.days_to_expiry) ? `${item.days_to_expiry} 天` : '-';
            const bidAsk = `${formatPrice(item.bid_price)} / ${formatPrice(item.ask_price)}`;
            const markPrice = formatPrice(item.mark_price);
            const ivLabel = formatPercent(item.iv);
            const deltaLabel = formatGreek(item.delta);
            const addedAt = formatAddedAt(item.added_at);
            const lastUpdatedValue = formatAddedAt(item.last_updated);
            const lastUpdated = lastUpdatedValue === '-' ? null : lastUpdatedValue;
            const inMoneyState = item.in_the_money;

            let itmLabel = '-';
            let itmClass = 'bg-secondary';
            if (inMoneyState === true) {
                itmLabel = '价内';
                itmClass = 'bg-success';
            } else if (inMoneyState === false) {
                itmLabel = '价外';
                itmClass = 'bg-secondary';
            } else if (inMoneyState === null || inMoneyState === undefined) {
                itmClass = 'bg-light text-dark';
                itmLabel = '未知';
            }

            if (item.stale) {
                row.classList.add('table-warning');
            }

            row.innerHTML = `
                <td><span class="contract-symbol">${item.symbol || '-'}</span></td>
                <td class="numeric-value">${strikePrice}</td>
                <td>${expiryLabel || '-'}</td>
                <td class="text-center">${daysLabel}</td>
                <td class="numeric-value">${bidAsk}</td>
                <td class="numeric-value">${markPrice}</td>
                <td class="numeric-value">${ivLabel}</td>
                <td class="numeric-value">${deltaLabel}</td>
                <td class="text-center">
                    <span class="badge ${itmClass}">${itmLabel}</span>
                </td>
                <td>
                    <div>${addedAt}</div>
                    ${lastUpdated ? `<div class="text-muted small">${item.stale ? '上次可用' : '更新'}: ${lastUpdated}</div>` : ''}
                    ${item.stale ? '<div class="text-warning small"><i class="bi bi-exclamation-triangle"></i> 暂无最新行情</div>' : ''}
                </td>
            `;

            watchlistTable.appendChild(row);
        });
    }

    function refreshWatchButtons() {
        const buttons = document.querySelectorAll('.watchlist-btn');
        buttons.forEach(button => updateWatchButtonState(button));
    }

    function updateWatchButtonState(button) {
        if (!button) {
            return;
        }
        const symbol = button.getAttribute('data-watch-symbol');
        const isWatched = watchlistState.symbols.has(symbol);

        if (isWatched) {
            button.classList.remove('btn-outline-warning');
            button.classList.add('btn-warning', 'text-dark');
            button.innerHTML = '<i class="bi bi-star-fill"></i> 已关注';
            button.disabled = true;
        } else {
            button.classList.add('btn-outline-warning');
            button.classList.remove('btn-warning', 'text-dark');
            button.innerHTML = '<i class="bi bi-star"></i> 关注';
            button.disabled = false;
        }
    }

    function setupWatchButton(button, option) {
        if (!button) {
            return;
        }

        button.addEventListener('click', () => handleAddToWatchlist(option, button));
        updateWatchButtonState(button);
    }

    async function handleAddToWatchlist(option, triggerButton) {
        if (!option || !option.symbol) {
            showErrorToast('关注失败', '缺少合约信息，无法加入关注');
            return;
        }

        const originalHtml = triggerButton.innerHTML;
        triggerButton.disabled = true;
        triggerButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>处理中...';

        try {
            const response = await fetch('/watchlist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ option })
            });

            const result = await response.json();

            if (result.success) {
                showSuccessToast('已添加关注', result.message || `${option.symbol} 已加入关注列表`);
                updateWatchlistDisplay(result.watchlist || []);
            } else {
                showErrorToast('关注失败', result.message || '请稍后再试');
                triggerButton.innerHTML = originalHtml;
            }
        } catch (error) {
            console.error('加入关注列表错误:', error);
            showErrorToast('关注失败', '网络错误，请稍后重试');
            triggerButton.innerHTML = originalHtml;
        } finally {
            if (!watchlistState.symbols.has(option.symbol)) {
                triggerButton.disabled = false;
                updateWatchButtonState(triggerButton);
            } else {
                triggerButton.disabled = true;
                updateWatchButtonState(triggerButton);
            }
        }
    }

    async function handleClearWatchlist() {
        if (!confirm('确定要清空关注列表吗？')) {
            return;
        }

        try {
            const response = await fetch('/watchlist', {
                method: 'DELETE'
            });
            const result = await response.json();

            if (result.success) {
                showSuccessToast('已清空关注', result.message || '关注列表已清空');
                updateWatchlistDisplay([]);
            } else {
                showErrorToast('清空失败', result.message || '请稍后再试');
            }
        } catch (error) {
            console.error('清空关注列表错误:', error);
            showErrorToast('清空失败', '网络错误，请稍后重试');
        }
    }

    async function handleSearch(event) {
        event.preventDefault();
        
        // 显示加载指示器
        showLoading();
        hideResults();
        hideError();
        
        try {
            // 获取表单数据
            const formData = new FormData(searchForm);
            const searchParams = {
                base_coin: formData.get('base_coin'),
                direction: formData.get('direction'),
                target_price: parseFloat(formData.get('target_price')),
                days: parseInt(formData.get('days'))
            };

            // 验证输入
            if (!validateSearchParams(searchParams)) {
                return;
            }

            // 发送搜索请求
            const response = await fetch('/search_options', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(searchParams)
            });

            const result = await response.json();

            if (result.success) {
                displayResults(result);
            } else {
                showError(result.message || '搜索失败');
            }

        } catch (error) {
            console.error('搜索错误:', error);
            showError('网络错误，请检查连接后重试');
        } finally {
            hideLoading();
        }
    }

    function validateSearchParams(params) {
        if (!params.target_price || params.target_price <= 0) {
            showError('请输入有效的目标价格');
            return false;
        }

        if (!params.days || params.days < 0) {
            showError('请输入有效的天数');
            return false;
        }

        return true;
    }

    async function updateCurrentPrice() {
        const baseCoin = baseCoinSelect.value;
        currentPriceSpan.textContent = '加载中...';
        
        try {
            const response = await fetch(`/get_current_price/${baseCoin}`);
            const result = await response.json();
            
            if (result.success) {
                currentPriceSpan.textContent = `$${result.price.toLocaleString()}`;
            } else {
                currentPriceSpan.textContent = '获取失败';
            }
        } catch (error) {
            console.error('获取价格错误:', error);
            currentPriceSpan.textContent = '获取失败';
        }
    }

    async function loadStrikePrices() {
        const baseCoin = baseCoinSelect.value;
        
        // 清空现有选项
        targetPriceSelect.innerHTML = '<option value="">加载中...</option>';
        
        try {
            const response = await fetch(`/get_strike_prices/${baseCoin}`);
            const result = await response.json();
            
            if (result.success && result.strikes.length > 0) {
                // 清空并重新填充选项
                targetPriceSelect.innerHTML = '<option value="">选择执行价格...</option>';
                
                result.strikes.forEach(strike => {
                    const option = document.createElement('option');
                    option.value = strike.price;
                    
                    // 根据状态设置显示文本和样式
                    let statusText = '';
                    let className = '';
                    
                    switch(strike.status) {
                        case 'ATM':
                            statusText = ' (平值)';
                            className = 'atm-option';
                            break;
                        case 'ITM':
                            statusText = ' (价内)';
                            className = 'itm-option';
                            break;
                        case 'OTM':
                            statusText = ' (价外)';
                            className = 'otm-option';
                            break;
                    }
                    
                    option.textContent = `${strike.formatted}${statusText}`;
                    option.className = className;
                    
                    // 设置data属性用于排序和筛选
                    option.setAttribute('data-diff-pct', Math.abs(strike.diff_pct));
                    option.setAttribute('data-status', strike.status);
                    
                    targetPriceSelect.appendChild(option);
                });
                
                // 默认选择最接近的平值期权
                const atmOptions = result.strikes.filter(s => s.status === 'ATM');
                if (atmOptions.length > 0) {
                    targetPriceSelect.value = atmOptions[0].price;
                }
                
            } else {
                targetPriceSelect.innerHTML = '<option value="">暂无可用执行价格</option>';
            }
        } catch (error) {
            console.error('获取执行价格错误:', error);
            targetPriceSelect.innerHTML = '<option value="">获取失败</option>';
        }
    }

    async function showExpiryDates() {
        const baseCoin = baseCoinSelect.value;
        const modal = new bootstrap.Modal(document.getElementById('expiryDatesModal'));
        const datesList = document.getElementById('expiryDatesList');
        
        // 显示加载
        datesList.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">加载中...</span>
                </div>
                <p class="mt-2">正在获取可用日期...</p>
            </div>
        `;
        
        modal.show();
        
        try {
            const response = await fetch(`/get_expiry_dates/${baseCoin}`);
            const result = await response.json();
            
            if (result.success && result.dates.length > 0) {
                let html = '<div class="row">';
                
                result.dates.forEach((date, index) => {
                    let itemClass = 'expiry-date-item';
                    if (date.days <= 7) {
                        itemClass += ' very-soon';
                    } else if (date.days <= 30) {
                        itemClass += ' soon';
                    }
                    
                    html += `
                        <div class="col-12 mb-2">
                            <div class="${itemClass}" onclick="selectExpiryDate(${date.days})">
                                <div class="d-flex justify-content-between align-items-center">
                                    <span class="fw-bold">${date.date}</span>
                                    <span class="badge ${date.days <= 7 ? 'bg-danger' : date.days <= 30 ? 'bg-warning' : 'bg-primary'}">${date.days}天</span>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
                datesList.innerHTML = html;
            } else {
                datesList.innerHTML = '<div class="alert alert-info">暂无可用的到期日期</div>';
            }
        } catch (error) {
            console.error('获取日期错误:', error);
            datesList.innerHTML = '<div class="alert alert-danger">获取日期失败</div>';
        }
    }

    function displayResults(result) {
        const resultsTable = document.getElementById('resultsTable');
        const resultCount = document.getElementById('resultCount');
        const searchSummary = document.getElementById('searchSummary');
        
        // 更新结果数量
        resultCount.textContent = `${result.total_count} 个结果`;
        
        // 更新搜索摘要
        const params = result.search_params;
        searchSummary.innerHTML = `
            <strong>搜索条件:</strong> 
            ${params.base_coin} ${params.direction === 'Call' ? '看涨' : '看跌'}期权 | 
            目标价格: $${params.target_price.toLocaleString()} | 
            目标天数: ${params.days}天 | 
            搜索范围: ${params.date_range}
        `;
        
        // 清空表格
        resultsTable.innerHTML = '';
        
        if (result.options.length === 0) {
            resultsTable.innerHTML = `
                <tr>
                    <td colspan="15" class="text-center text-muted">
                        未找到符合条件的期权合约
                    </td>
                </tr>
            `;
        } else {
            // 添加结果行
            result.options.forEach((option, index) => {
                const row = createResultRow(option, index === 0);
                resultsTable.appendChild(row);
            });

            refreshWatchButtons();
        }
        
        // 显示结果
        showResults();
    }

    function createResultRow(option, isBestMatch) {
        const row = document.createElement('tr');
        if (isBestMatch) {
            row.classList.add('best-match');
        }
        
        // 判断IV等级
        const getIVClass = (iv) => {
            if (iv > 100) return 'iv-high';
            if (iv > 50) return 'iv-medium';
            return 'iv-low';
        };
        
        // 判断Delta颜色
        const getDeltaClass = (delta) => {
            return delta >= 0 ? 'greek-positive' : 'greek-negative';
        };
        
        row.innerHTML = `
            <td><span class="contract-symbol">${option.symbol}</span></td>
            <td class="numeric-value">$${option.strike_price.toLocaleString()}</td>
            <td class="numeric-value">$${option.price_diff.toFixed(0)}</td>
            <td class="numeric-value">${formatPercent(option.price_diff_pct)}</td>
            <td>${option.expiry_date_formatted}</td>
            <td class="text-center">
                <span class="badge ${option.days_to_expiry <= 7 ? 'bg-danger' : option.days_to_expiry <= 30 ? 'bg-warning' : 'bg-primary'}">
                    ${option.days_to_expiry}天
                </span>
            </td>
            <td class="numeric-value">${formatPrice(option.bid_price)}</td>
            <td class="numeric-value">${formatPrice(option.ask_price)}</td>
            <td class="numeric-value fw-bold">${formatPrice(option.mark_price)}</td>
            <td class="numeric-value">${formatVolume(option.volume_24h)}</td>
            <td class="numeric-value">${formatVolume(option.open_interest)}</td>
            <td class="numeric-value">
                <span class="${getIVClass(option.iv)}">${formatPercent(option.iv)}</span>
            </td>
            <td class="numeric-value">
                <span class="${getDeltaClass(option.delta)}">${formatGreek(option.delta)}</span>
            </td>
            <td class="text-center">
                <span class="badge ${option.in_the_money ? 'bg-success' : 'bg-secondary'}">
                    ${option.in_the_money ? '价内' : '价外'}
                </span>
            </td>
            <td class="text-center">
                <button type="button" class="btn btn-outline-warning btn-sm watchlist-btn" data-watch-symbol="${option.symbol}">
                    <i class="bi bi-star"></i> 关注
                </button>
            </td>
        `;
        
        const watchButton = row.querySelector('.watchlist-btn');
        setupWatchButton(watchButton, option);
        
        return row;
    }

    function showLoading() {
        loadingIndicator.classList.remove('d-none');
    }

    function hideLoading() {
        loadingIndicator.classList.add('d-none');
    }

    function showResults() {
        searchResults.classList.remove('d-none');
        searchResults.classList.add('fade-in');
    }

    function hideResults() {
        searchResults.classList.add('d-none');
        searchResults.classList.remove('fade-in');
    }

    function showError(message) {
        const errorText = document.getElementById('errorText');
        errorText.textContent = message;
        errorMessage.classList.remove('d-none');
        
        // 自动隐藏错误消息
        setTimeout(() => {
            hideError();
        }, 5000);
    }

    function hideError() {
        errorMessage.classList.add('d-none');
    }

    async function checkDataStatus() {
        const baseCoin = baseCoinSelect.value;
        
        try {
            const response = await fetch(`/get_cache_status/${baseCoin}`);
            const result = await response.json();
            
            if (result.success) {
                updateDataStatusDisplay(result);
                
                // 如果有缓存数据，加载执行价格
                if (result.cached && !result.is_expired) {
                    loadStrikePrices();
                }
            } else {
                showDataStatusError('检查数据状态失败');
            }
        } catch (error) {
            console.error('检查数据状态错误:', error);
            showDataStatusError('检查数据状态失败');
        }
    }

    function updateDataStatusDisplay(status) {
        if (status.cached) {
            if (status.is_expired) {
                dataStatusBar.className = 'alert alert-warning mb-4';
                dataStatusText.innerHTML = '<i class="bi bi-exclamation-triangle"></i> 数据已过期，建议刷新';
            } else {
                dataStatusBar.className = 'alert alert-success mb-4';
                dataStatusText.innerHTML = '<i class="bi bi-check-circle"></i> 数据是最新的';
            }
            
            dataStatusDetails.textContent = `缓存时间: ${status.cache_time} | 合约: ${status.total_contracts} | 执行价: ${status.strike_prices_count} | 到期日: ${status.expiry_dates_count}`;
        } else {
            dataStatusBar.className = 'alert alert-danger mb-4';
            dataStatusText.innerHTML = '<i class="bi bi-exclamation-circle"></i> 暂无数据，请刷新获取';
            dataStatusDetails.textContent = '点击右上角"刷新数据"按钮获取最新期权数据';
        }
    }

    function showDataStatusError(message) {
        dataStatusBar.className = 'alert alert-danger mb-4';
        dataStatusText.innerHTML = `<i class="bi bi-exclamation-circle"></i> ${message}`;
        dataStatusDetails.textContent = '';
    }

    async function refreshData() {
        const baseCoin = baseCoinSelect.value;
        
        // 显示刷新状态
        refreshDataBtn.disabled = true;
        refreshDataBtn.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> 刷新中...';
        
        dataStatusBar.className = 'alert alert-info mb-4';
        dataStatusText.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> 正在刷新数据，请稍候...';
        dataStatusDetails.textContent = '这可能需要几秒钟时间';
        
        try {
            const response = await fetch(`/refresh_data/${baseCoin}`);
            const result = await response.json();
            
            if (result.success) {
                // 刷新成功
                dataStatusBar.className = 'alert alert-success mb-4';
                dataStatusText.innerHTML = '<i class="bi bi-check-circle"></i> 数据刷新成功！';
                dataStatusDetails.textContent = `更新时间: ${result.stats.refresh_time} | 合约: ${result.stats.total_contracts} | 执行价: ${result.stats.strike_prices_count} | 到期日: ${result.stats.expiry_dates_count}`;
                
                // 重新加载执行价格
                loadStrikePrices();
                await loadWatchlist();
                
                // 显示成功消息
                showSuccessToast('数据刷新成功', `获取了 ${result.stats.total_contracts} 个期权合约`);
            } else {
                // 刷新失败
                dataStatusBar.className = 'alert alert-danger mb-4';
                dataStatusText.innerHTML = '<i class="bi bi-exclamation-circle"></i> 数据刷新失败';
                dataStatusDetails.textContent = result.message;
                
                showErrorToast('刷新失败', result.message);
            }
        } catch (error) {
            console.error('刷新数据错误:', error);
            dataStatusBar.className = 'alert alert-danger mb-4';
            dataStatusText.innerHTML = '<i class="bi bi-exclamation-circle"></i> 网络错误';
            dataStatusDetails.textContent = '请检查网络连接后重试';
            
            showErrorToast('网络错误', '请检查网络连接后重试');
        } finally {
            // 恢复按钮状态
            refreshDataBtn.disabled = false;
            refreshDataBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新数据';
        }
    }

    function showSuccessToast(title, message) {
        const toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="toast show bg-success text-white" role="alert">
                <div class="toast-header bg-success text-white border-0">
                    <i class="bi bi-check-circle-fill me-2"></i>
                    <strong class="me-auto">${title}</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
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
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }

    // 全局函数，供HTML调用
    window.selectExpiryDate = function(days) {
        document.getElementById('days').value = days;
        bootstrap.Modal.getInstance(document.getElementById('expiryDatesModal')).hide();
        
        // 显示成功提示
        const toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="toast show" role="alert">
                <div class="toast-header">
                    <i class="bi bi-check-circle-fill text-success me-2"></i>
                    <strong class="me-auto">设置成功</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    已设置目标天数为 ${days} 天
                </div>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    };

    // 添加键盘快捷键支持
    document.addEventListener('keydown', function(event) {
        // Ctrl/Cmd + Enter 执行搜索
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            searchForm.dispatchEvent(new Event('submit'));
        }
        
        // F5 刷新当前价格
        if (event.key === 'F5') {
            event.preventDefault();
            updateCurrentPrice();
        }
    });

    // 添加输入验证
    if (targetPriceSelect) {
        targetPriceSelect.addEventListener('change', function() {
            const value = parseFloat(this.value);
            if (!Number.isFinite(value) || value < 0) {
                this.value = '';
            }
        });
    }

    document.getElementById('days').addEventListener('input', function() {
        const value = parseInt(this.value);
        if (value < 0) {
            this.value = 0;
        } else if (value > 365) {
            this.value = 365;
        }
    });

    // 添加工具提示
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
