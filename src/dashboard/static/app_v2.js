/**
 * Crypto Trader Pro - Dashboard Frontend (SPA)
 * 多页面路由 + API 调用
 */

const API_BASE = '';
const REFRESH_INTERVAL = 5000;

let balanceHistory = [];
let chartInstance = null;

// 页面路由
document.addEventListener('DOMContentLoaded', () => {
    initRouter();
    startPolling();
    fetchAllData();
    bindEvents();
});

function initRouter() {
    const links = document.querySelectorAll('.nav-links a');
    const pages = document.querySelectorAll('.page');

    links.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const pageId = link.getAttribute('data-page');
            switchPage(pageId);
        });
    });
}

function switchPage(pageId) {
    // 更新导航激活状态
    document.querySelectorAll('.nav-links a').forEach(a => {
        a.classList.toggle('active', a.getAttribute('data-page') === pageId);
    });
    // 显示对应页面
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === pageId);
    });
    // 页面特定初始化
    if (pageId === 'logs') {
        fetchLogs();
        connectLogStream();
    }
    if (pageId === 'strategies') {
        loadStrategies();
    }
    if (pageId === 'dashboard' || pageId === 'trades') {
        fetchAllData();
    }
}

// 轮询数据（概览页）
function startPolling() {
    setInterval(() => {
        if (document.getElementById('dashboard').classList.contains('active')) {
            fetchAllData();
        }
    }, REFRESH_INTERVAL);
}

async function fetchAllData() {
    await Promise.all([
        fetchStatus(),
        fetchBalance(),
        fetchPositions(),
        fetchTrades(),
        fetchDailyPnl()
    ]);
    updateLastUpdateTime();
}

function showLoading(id) {
    const el = document.getElementById(id + '-loading');
    const table = document.getElementById(id + '-table');
    const empty = document.getElementById(id + '-empty');
    if (el) el.style.display = 'block';
    if (table) table.style.display = 'none';
    if (empty) empty.style.display = 'none';
}

function hideLoading(id, hasData) {
    const el = document.getElementById(id + '-loading');
    const table = document.getElementById(id + '-table');
    const empty = document.getElementById(id + '-empty');
    if (el) el.style.display = 'none';
    if (table) table.style.display = hasData ? 'table' : 'none';
    if (empty) empty.style.display = hasData ? 'none' : 'block';
}

async function fetchStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/status`);
        const data = await res.json();
        document.getElementById('mode-badge').textContent = data.mode;
        // Trader 状态
        const traderRes = await fetch(`${API_BASE}/api/trader/status`);
        const trader = await traderRes.json();
        document.getElementById('toggle-trader').textContent = trader.running ? '停止' : '启动';
        updateTraderStats(trader);
    } catch (e) {
        console.error('获取状态失败:', e);
    }
}

function updateTraderStats(trader) {
    document.getElementById('bal').textContent = 'N/A'; // 余额需另外接口
    document.getElementById('total-pnl').textContent = (trader.total_pnl >= 0 ? '+' : '') + trader.total_pnl.toFixed(2);
    document.getElementById('total-pnl').className = trader.total_pnl >= 0 ? 'positive' : 'negative';
    document.getElementById('open-positions').textContent = trader.open_trades_count;
    document.getElementById('today-trades').textContent = trader.closed_trades_count;

    // 控制按钮文本与事件
    const btn = document.getElementById('toggle-trader');
    if (btn) {
        btn.textContent = trader.running ? '停止' : '启动';
        btn.onclick = async () => {
            const action = trader.running ? 'stop' : 'start';
            try {
                const res = await fetch(`${API_BASE}/api/trader/control`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action})
                });
                const data = await res.json();
                if (data.success) {
                    setTimeout(fetchStatus, 1000); // 1秒后刷新状态
                } else {
                    alert('操作失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                console.error('控制交易器失败', e);
                alert('网络错误');
            }
        };
    }
}

async function fetchBalance() {
    try {
        const res = await fetch(`${API_BASE}/api/balance`);
        const data = await res.json();
        const usdt = data.USDT || 0;
        document.getElementById('balance').textContent = `$${usdt.toFixed(2)}`;
        document.getElementById('balance2').textContent = `$${usdt.toFixed(2)}`;
        // 记录图表数据
        const now = new Date();
        balanceHistory.push({ time: now.toLocaleTimeString(), balance: usdt });
        if (balanceHistory.length > 20) balanceHistory.shift();
        updateBalanceChart();
    } catch (e) {
        console.error('获取余额失败:', e);
    }
}

async function fetchPositions() {
    showLoading('positions');
    try {
        const res = await fetch(`${API_BASE}/api/positions`);
        const positions = await res.json();
        const tbody = document.getElementById('positions-body');
        if (positions.length === 0) {
            hideLoading('positions', false);
        } else {
            tbody.innerHTML = positions.map(pos => {
                const sideClass = pos.side === 'long' ? 'positive' : 'negative';
                const sideText = pos.side === 'long' ? '多' : '空';
                const upnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
                const upnlText = pos.unrealized_pnl >= 0 ? `+${pos.unrealized_pnl.toFixed(2)}` : `${pos.unrealized_pnl.toFixed(2)}`;
                return `
                    <tr>
                        <td>${pos.symbol}</td>
                        <td class="${sideClass}">${sideText}</td>
                        <td>${pos.quantity.toFixed(6)}</td>
                        <td>${pos.entry_price.toFixed(2)}</td>
                        <td>${pos.current_price.toFixed(2)}</td>
                        <td class="${upnlClass}">$${upnlText}</td>
                    </tr>
                `;
            }).join('');
            hideLoading('positions', true);
        }
    } catch (e) {
        console.error('获取持仓失败:', e);
        hideLoading('positions', false);
    }
}

async function fetchTrades() {
    showLoading('trades');
    try {
        const res = await fetch(`${API_BASE}/api/trades?limit=10`);
        const trades = await res.json();
        const tbody = document.getElementById('trades-body');
        if (trades.length === 0) {
            hideLoading('trades', false);
        } else {
            tbody.innerHTML = trades.map(trade => {
                const sideClass = trade.side === 'buy' ? 'positive' : 'negative';
                const sideText = trade.side === 'buy' ? '买入' : '卖出';
                const pnl = trade.pnl || 0;
                const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                const pnlText = pnl >= 0 ? `+${pnl.toFixed(2)}` : `${pnl.toFixed(2)}`;
                const time = trade.executed_at ? new Date(trade.executed_at).toLocaleString() : '-';
                return `
                    <tr>
                        <td>${time}</td>
                        <td>${trade.symbol}</td>
                        <td class="${sideClass}">${sideText}</td>
                        <td>${trade.quantity.toFixed(6)}</td>
                        <td>${trade.price.toFixed(2)}</td>
                        <td class="${pnlClass}">$${pnlText}</td>
                    </tr>
                `;
            }).join('');
            hideLoading('trades', true);
        }
    } catch (e) {
        console.error('获取交易失败:', e);
        hideLoading('trades', false);
    }
}

async function fetchDailyPnl() {
    try {
        const res = await fetch(`${API_BASE}/api/pnl/daily`);
        const data = await res.json();
        const pnl = data.total_pnl || 0;
        const el = document.getElementById('daily-pnl');
        const isPos = pnl >= 0;
        el.className = isPos ? 'positive' : 'negative';
        el.textContent = `${isPos ? '+' : ''}$${pnl.toFixed(2)}`;
    } catch (e) {
        console.error('获取盈亏失败:', e);
    }
}

function updateBalanceChart() {
    const ctx = document.getElementById('balanceChart').getContext('2d');
    const labels = balanceHistory.map(h => h.time);
    const data = balanceHistory.map(h => h.balance);

    if (chartInstance) {
        chartInstance.data.labels = labels;
        chartInstance.data.datasets[0].data = data;
        chartInstance.update('none');
    } else {
        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'USDT 余额',
                    data,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102,126,234,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { grid: { display: false } }, y: { grid: { color: 'rgba(0,0,0,0.05)' } } }
            }
        });
    }
}

// 交易表单
function bindEvents() {
    // 交易表单
    const form = document.getElementById('trade-form');
    const resultDiv = document.getElementById('trade-result');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const side = document.getElementById('trade-side').value;
            const quantity = parseFloat(document.getElementById('trade-quantity').value);
            if (!quantity || quantity <= 0) {
                resultDiv.textContent = '❌ 请输入有效的数量';
                resultDiv.style.color = '#ef4444';
                return;
            }
            resultDiv.textContent = '⏳ 提交中...';
            resultDiv.style.color = '#333';
            try {
                const resp = await fetch(`${API_BASE}/api/order`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ side, quantity })
                });
                const data = await resp.json();
                if (resp.ok && data.success) {
                    resultDiv.innerHTML = `✅ 订单成功<br>ID: ${data.order_id}<br>成交均价: $${data.avg_price.toFixed(2)}<br>数量: ${data.filled_quantity}<br>手续费: $${data.fee.toFixed(4)}`;
                    resultDiv.style.color = '#10b981';
                    form.reset();
                    setTimeout(fetchAllData, 2000);
                } else {
                    resultDiv.innerHTML = `❌ 下单失败: ${data.error || '未知错误'}`;
                    resultDiv.style.color = '#ef4444';
                }
            } catch (err) {
                resultDiv.innerHTML = `❌ 网络错误: ${err.message}`;
                resultDiv.style.color = '#ef4444';
            }
        });
    }

    // 策略重载按钮
    document.getElementById('reload-strategy-btn')?.addEventListener('click', async () => {
        const statusDiv = document.getElementById('strategy-status');
        statusDiv.textContent = '重载中...';
        try {
            const resp = await fetch(`${API_BASE}/api/strategy/reload`, { method: 'POST' });
            const data = await resp.json();
            if (resp.ok) {
                statusDiv.textContent = `✅ ${data.message}`;
                fetchStrategyInfo();
            } else {
                statusDiv.textContent = `❌ ${data.error}`;
            }
        } catch (e) {
            statusDiv.textContent = `❌ 网络错误`;
        }
    });

    // 保存设置按钮
    document.getElementById('save-settings-btn')?.addEventListener('click', async () => {
        const exchange = document.getElementById('setting-exchange').value;
        const notify = document.getElementById('setting-notify').value;
        const statusDiv = document.getElementById('settings-status');
        try {
            const resp = await fetch(`${API_BASE}/api/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ exchange, notifications_enabled: notify === 'true' })
            });
            const data = await resp.json();
            statusDiv.textContent = resp.ok ? `✅ ${data.message}` : `❌ ${data.error}`;
        } catch (e) {
            statusDiv.textContent = `❌ 网络错误`;
        }
    });

    // 回测表单
    const backtestForm = document.getElementById('backtest-form');
    if (backtestForm) {
        backtestForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const resultDiv = document.getElementById('backtest-result');
            resultDiv.textContent = '⏳ 回测进行中...';
            try {
                const strategy = document.getElementById('backtest-strategy').value;
                const days = parseInt(document.getElementById('backtest-days').value);
                const initial = parseFloat(document.getElementById('backtest-initial').value);
                const resp = await fetch(`${API_BASE}/api/backtest`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strategy, days, initial_balance: initial })
                });
                const data = await resp.json();
                if (resp.ok) {
                    resultDiv.innerHTML = `
                        <p><strong>策略:</strong> ${data.strategy}</p>
                        <p><strong>初始/最终资产:</strong> $${data.initial_balance} → $${data.final_equity.toFixed(2)}</p>
                        <p><strong>总收益率:</strong> ${data.total_return_pct}%</p>
                        <p><strong>最大回撤:</strong> ${data.max_drawdown_pct}%</p>
                        <p><strong>交易笔数:</strong> ${data.trades_count}</p>
                    `;
                    // 绘制资金曲线
                    renderEquityChart(data.equity_curve);
                } else {
                    resultDiv.innerHTML = `❌ 回测失败: ${data.error || '未知错误'}`;
                }
            } catch (err) {
                resultDiv.innerHTML = `❌ 网络错误: ${err.message}`;
            }
        });
    }
}

// 绘制资金曲线
function renderEquityChart(equityData) {
    const canvas = document.getElementById('backtestChart');
    if (!canvas) return;
    canvas.style.display = 'block';
    const ctx = canvas.getContext('2d');
    const labels = equityData.map(d => new Date(d.time).toLocaleDateString());
    const data = equityData.map(d => d.equity);
    if (window.backtestChart) window.backtestChart.destroy();
    window.backtestChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '资产 (USDT)',
                data,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16,185,129,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: true } },
            scales: { x: { grid: { display: false } }, y: { grid: { color: 'rgba(0,0,0,0.05)' } } }
        }
    });
}

// 页面加载时额外获取数据
async function fetchStrategyInfo() {
    try {
        const res = await fetch(`${API_BASE}/api/strategy`);
        const data = await res.json();
        document.getElementById('current-strategy-name').textContent = data.name || '-';
        const paramsDiv = document.getElementById('strategy-params');
        paramsDiv.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
    } catch (e) {
        console.error('获取策略信息失败:', e);
    }
}

// 日志轮询（切换到日志页时启动）
let logPolling = null;
function startLogPolling() {
    if (logPolling) clearInterval(logPolling);
    logPolling = setInterval(fetchLogs, 3000);
}
document.addEventListener('DOMContentLoaded', () => {
    // 监听页面切换
    const observer = new MutationObserver(() => {
        const logsPage = document.getElementById('logs');
        if (logsPage.classList.contains('active')) {
            fetchLogs();
            startLogPolling();
        } else {
            clearInterval(logPolling);
        }
    });
    observer.observe(document.body, { attributes: true, childList: true, subtree: true });
});

async function fetchStrategyInfo() {
    try {
        const res = await fetch(`${API_BASE}/api/strategy`);
        const data = await res.json();
        document.getElementById('current-strategy-name').textContent = data.name || '-';
        const paramsDiv = document.getElementById('strategy-params');
        paramsDiv.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
    } catch (e) {
        console.error('获取策略信息失败:', e);
    }
}

// 实时日志流（SSE）
function connectLogStream() {
    const logDiv = document.getElementById('log-content');
    if (!logDiv) return;
    const evtSource = new EventSource(`${API_BASE}/api/logs/stream`);
    evtSource.onmessage = (event) => {
        const line = event.data;
        logDiv.textContent += line + '\n';
        logDiv.scrollTop = logDiv.scrollHeight;
    };
    evtSource.onerror = (e) => {
        console.error('日志流断开，3秒后重连...', e);
        setTimeout(connectLogStream, 3000);
    };
}

// 加载并渲染策略列表（支持内联编辑）
async function loadStrategies() {
    try {
        const res = await fetch(`${API_BASE}/api/strategies`);
        const strategies = await res.json();
        const container = document.getElementById('strategies-list');
        container.innerHTML = '';
        for (const strat of strategies) {
            const card = document.createElement('div');
            card.className = 'card';
            card.style.marginBottom = '10px';
            // 构建参数编辑区
            let paramsHtml = '';
            const config = strat.config || {};
            // 常见参数：position_size, stop_loss_pct, take_profit_pct, fast_period, slow_period, rsi_period, bb_period, bb_std 等
            const commonParams = [
                {key: 'position_size', label: '仓位比例', type: 'number', step: 0.01},
                {key: 'stop_loss_pct', label: '止损%', type: 'number', step: 0.01},
                {key: 'take_profit_pct', label: '止盈%', type: 'number', step: 0.01}
            ];
            // 根据策略类型添加特定参数
            if (strat.type === 'ma_cross') {
                commonParams.push({key: 'fast_period', label: '快线周期', type: 'number'});
                commonParams.push({key: 'slow_period', label: '慢线周期', type: 'number'});
            } else if (strat.type === 'rsi') {
                commonParams.push({key: 'rsi_period', label: 'RSI周期', type: 'number'});
                commonParams.push({key: 'oversold', label: '超卖线', type: 'number'});
                commonParams.push({key: 'overbought', label: '超买线', type: 'number'});
            } else if (strat.type === 'bollinger') {
                commonParams.push({key: 'bb_period', label: '布林带周期', type: 'number'});
                commonParams.push({key: 'bb_std', label: '标准差倍数', type: 'number', step: 0.1});
            } else if (strat.type === 'macd') {
                commonParams.push({key: 'fast_period', label: '快线周期', type: 'number'});
                commonParams.push({key: 'slow_period', label: '慢线周期', type: 'number'});
                commonParams.push({key: 'signal_period', label: '信号线周期', type: 'number'});
            }
            for (const param of commonParams) {
                const val = config[param.key] !== undefined ? config[param.key] : (config.params ? config.params[param.key] : '');
                paramsHtml += `
                    <div class="form-group">
                        <label>${param.label}</label>
                        <input type="${param.type}" step="${param.step||1}" 
                               data-strat="${strat.file}" data-param="${param.key}"
                               value="${val}" class="strategy-param-input" style="width:100%; padding:4px;">
                    </div>`;
            }
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h4>${strat.name} (${strat.type})</h4>
                    <button class="btn btn-sm save-strategy-btn" data-file="${strat.file}">保存配置</button>
                </div>
                <div class="strategy-params" style="margin-top:10px; display:grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap:10px;">
                    ${paramsHtml}
                </div>
                <div class="save-status" style="margin-top:5px; color: #10b981; font-size: 0.9rem;"></div>
            `;
            container.appendChild(card);
        }
        // 绑定保存按钮事件
        document.querySelectorAll('.save-strategy-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const file = btn.dataset.file;
                const inputs = btn.closest('.card').querySelectorAll('.strategy-param-input');
                const newConfig = {};
                inputs.forEach(inp => {
                    const key = inp.dataset.param;
                    const val = parseFloat(inp.value) || inp.value;
                    newConfig[key] = val;
                });
                try {
                    const res = await fetch(`${API_BASE}/api/strategy/config`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({file, config: newConfig})
                    });
                    const result = await res.json();
                    if (result.success) {
                        btn.closest('.card').querySelector('.save-status').textContent = '✅ 已保存';
                        setTimeout(() => btn.closest('.card').querySelector('.save-status').textContent = '', 2000);
                    } else {
                        alert('保存失败: ' + (result.error || '未知错误'));
                    }
                } catch (e) {
                    console.error('保存策略配置失败', e);
                    alert('网络错误');
                }
            });
        });
    } catch (e) {
        console.error('加载策略列表失败:', e);
    }
}

async function fetchLogs() {
    try {
        const res = await fetch(`${API_BASE}/api/logs?lines=200`);
        const data = await res.json();
        document.getElementById('log-content').textContent = data.logs || '暂无日志';
    } catch (e) {
        document.getElementById('log-content').textContent = '获取日志失败';
    }
}

function updateLastUpdateTime() {
    // 可以加一个全局最后更新时间显示
}