// Application settings management

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('apiSettingsForm');
    if (!form) {
        return;
    }

    const apiKeyInput = document.getElementById('apiKeyInput');
    const apiSecretInput = document.getElementById('apiSecretInput');
    const envTestnetRadio = document.getElementById('envTestnet');
    const envLiveRadio = document.getElementById('envLive');
    const priceMonitorInput = document.getElementById('priceMonitorInput');
    const webhookBaseInput = document.getElementById('webhookBaseInput');
    const saveBtn = document.getElementById('saveSettingsBtn');
    const statusText = document.getElementById('settingsStatus');

    let currentSettings = null;

    init();

    function init() {
        loadSettings();
        bindEvents();
    }

    function bindEvents() {
        saveBtn.addEventListener('click', handleSave);
    }

    async function loadSettings() {
        statusText.textContent = '加载设置中...';
        try {
            const response = await fetch('/api/settings');
            const result = await response.json();
            if (result.success) {
                currentSettings = result.settings;
                applySettingsToForm(result.settings);
                statusText.textContent = '设置已加载';
            } else {
                statusText.textContent = result.message || '加载失败';
            }
        } catch (error) {
            console.error('加载设置失败:', error);
            statusText.textContent = '加载失败，请检查网络连接';
        }
    }

    function applySettingsToForm(settings) {
        apiKeyInput.value = settings.api_key || '';
        apiSecretInput.value = settings.api_secret || '';
        if (settings.is_testnet) {
            envTestnetRadio.checked = true;
        } else {
            envLiveRadio.checked = true;
        }
        priceMonitorInput.value = settings.price_monitor_base || 'http://localhost:8888';
        webhookBaseInput.value = settings.strategy_webhook_base || 'http://localhost:8080';
    }

    async function handleSave() {
        if (!form.reportValidity()) {
            return;
        }

        const payload = {
            api_key: apiKeyInput.value.trim(),
            api_secret: apiSecretInput.value.trim(),
            is_testnet: envTestnetRadio.checked,
            price_monitor_base: (priceMonitorInput.value || 'http://localhost:8888').trim(),
            strategy_webhook_base: (webhookBaseInput.value || 'http://localhost:8080').trim(),
        };

        if (!payload.api_key || !payload.api_secret) {
            showErrorToast('保存失败', 'API Key 和 Secret 不能为空');
            return;
        }

        saveBtn.disabled = true;
        statusText.textContent = '正在保存...';

        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
            const result = await response.json();
            if (result.success) {
                currentSettings = result.settings;
                applySettingsToForm(result.settings);
                statusText.textContent = '保存成功，配置已应用';
                showSuccessToast('保存成功', '新的 API 配置已生效');
            } else {
                statusText.textContent = result.message || '保存失败';
                showErrorToast('保存失败', result.message || '请稍后再试');
            }
        } catch (error) {
            console.error('保存设置失败:', error);
            statusText.textContent = '保存失败，请检查网络连接';
            showErrorToast('保存失败', '网络错误');
        } finally {
            saveBtn.disabled = false;
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
                <div class="toast-body">${message}</div>
            </div>
        `;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
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
        setTimeout(() => toast.remove(), 5000);
    }
});
