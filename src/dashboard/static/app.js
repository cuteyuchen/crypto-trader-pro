/**
 * Crypto Trader Pro - Dashboard Frontend
 * 轮询 API，实时更新数据
 */

// 配置
const API_BASE = ''; // 相对路径
const REFRESH_INTERVAL = 5000; // 5秒

// 全局变量
let balanceChart = null;
let balanceHistory = []; // 存储余额历史 [{time: string, balance: number}]

// 页面加载完成后启动轮询
document.addEventListener('DOMContentLoaded', () => {
    startPolling();
});

/**
 * 启动定时轮询
 */
function startPolling() {
    fetchData(); // 立即 fetch 一次
    setInterval(fetchData, REFRESH_INTERVAL);
}

/**
 * 统一 fetch 所有数据
 */
async function fetchData() {
    try {
        await Promise.all([
            fetchStatus(),
            fetchBalance(),
            fetchPositions(),
            fetchTrades(),
            fetchDailyPnl(),
            fetchStrategyStatus()
        ]);
        updateLastUpdateTime();
    } catch (error) {
        console.error('获取数据失败:', error);
    }
}

/**
 * 获取运行状态
 */
async function fetchStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/status`);
        const data = await res.json();
        
        document.getElementById('mode').textContent = data.mode;
        document.getElementById('running').textContent = data.running ? '✅ 运行中' : '⏸ 已停止';
        document.getElementById('initial-balance').textContent = `$${data.initial_balance.toFixed(2)}`;
    } catch (e) {
        console.error('获取状态失败:', e);
    }
}

/**
 * 获取余额
 */
async function fetchBalance() {
    try {
        const res = await fetch(`${API_BASE}/api/balance`);
        const data = await res.json();
        const balance = data.USDT || 0;
        
        const el = document.getElementById('balance');
        const loading = document.getElementById('balance-loading');
        loading.style.display = 'none';
        el.textContent = `$${balance.toFixed(2)}`;
        
        // 记录余额历史
        const now = new Date();
        balanceHistory.push({
            time: now.toLocaleTimeString(),
            balance: balance
        });
        // 只保留最近 20 个点
        if (balanceHistory.length > 20) {
            balanceHistory.shift();
        }
        updateBalanceChart();
    } catch (e) {
        console.error('获取余额失败:', e);
    }
}

/**
 * 获取持仓
 */
async function fetchPositions() {
    try {
        const res = await fetch(`${API_BASE}/api/positions`);
        const positions = await res.json();
        
        const table = document.getElementById('positions-table');
        const empty = document.getElementById('positions-empty');
        const loading = document.getElementById('positions-loading');
        const tbody = document.getElementById('positions-body');
        
        loading.style.display = 'none';
        
        if (positions.length === 0) {
            table.style.display = 'none';
            empty.style.display = 'block';
        } else {
            table.style.display = 'table';
            empty.style.display = 'none';
            
            tbody.innerHTML = positions.map(pos => {
                const sideClass = pos.side === 'long' ? 'positive' : 'negative';
                const sideText = pos.side === 'long' ? '多' : '空';
                const upnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
                const upnlText = pos.unrealized_pnl >= 0 ? `+$${pos.unrealized_pnl.toFixed(2)}` : `-$${Math.abs(pos.unrealized_pnl).toFixed(2)}`;
                const createdAt = new Date(pos.created_at).toLocaleString();
                
                return `
                    <tr>
                        <td>${pos.symbol}</td>
                        <td class="${sideClass}">${sideText}</td>
                        <td>${pos.quantity.toFixed(6)}</td>
                        <td>$${pos.entry_price.toFixed(2)}</td>
                        <td>$${pos.current_price.toFixed(2)}</td>
                        <td class="${upnlClass}">${upnlText}</td>
                        <td>${createdAt}</td>
                    </tr>
                `;
            }).join('');
        }
    } catch (e) {
        console.error('获取持仓失败:', e);
    }
}

/**
 * 获取最近交易
 */
async function fetchTrades() {
    try {
        const res = await fetch(`${API_BASE}/api/trades?limit=10`);
        const trades = await res.json();
        
        const table = document.getElementById('trades-table');
        const empty = document.getElementById('trades-empty');
        const loading = document.getElementById('trades-loading');
        const tbody = document.getElementById('trades-body');
        
        loading.style.display = 'none';
        
        if (trades.length === 0) {
            table.style.display = 'none';
            empty.style.display = 'block';
        } else {
            table.style.display = 'table';
            empty.style.display = 'none';
            
            tbody.innerHTML = trades.map(trade => {
                const sideClass = trade.side === 'buy' ? 'positive' : 'negative';
                const sideText = trade.side === 'buy' ? '买入' : '卖出';
                const pnl = trade.pnl || 0;
                const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                const pnlText = pnl >= 0 ? `+$${pnl.toFixed(2)}` : `-$${Math.abs(pnl).toFixed(2)}`;
                const executedAt = new Date(trade.executed_at).toLocaleString();
                
                return `
                    <tr>
                        <td>${executedAt}</td>
                        <td>${trade.symbol}</td>
                        <td class="${sideClass}">${sideText}</td>
                        <td>${trade.quantity.toFixed(6)}</td>
                        <td>$${trade.price.toFixed(2)}</td>
                        <td>$${trade.fee.toFixed(4)}</td>
                        <td class="${pnlClass}">${pnlText}</td>
                    </tr>
                `;
            }).join('');
        }
    } catch (e) {
        console.error('获取交易失败:', e);
    }
}

/**
 * 获取今日盈亏
 */
async function fetchDailyPnl() {
    try {
        const res = await fetch(`${API_BASE}/api/pnl/daily`);
        const data = await res.json();
        const pnl = data.total_pnl || 0;
        
        const el = document.getElementById('daily-pnl');
        const loading = document.getElementById('pnl-loading');
        loading.style.display = 'none';
        
        const isPositive = pnl >= 0;
        el.className = isPositive ? 'positive' : 'negative';
        el.textContent = `${isPositive ? '+' : ''}$${pnl.toFixed(2)}`;
    } catch (e) {
        console.error('获取盈亏失败:', e);
    }
}

/**
 * 获取策略状态
 */
async function fetchStrategyStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/strategy`);
        const data = await res.json();
        
        document.getElementById('strategy-state').textContent = data.state || '-';
        document.getElementById('kline-count').textContent = data.kline_count || '-';
    } catch (e) {
        console.error('获取策略状态失败:', e);
    }
}

/**
 * 更新最后刷新时间
 */
function updateLastUpdateTime() {
    const now = new Date();
    document.getElementById('last-update').textContent = now.toLocaleTimeString();
}

/**
 * 更新余额走势图
 */
function updateBalanceChart() {
    const ctx = document.getElementById('balanceChart').getContext('2d');
    
    const labels = balanceHistory.map(item => item.time);
    const data = balanceHistory.map(item => item.balance);
    
    if (balanceChart) {
        balanceChart.data.labels = labels;
        balanceChart.data.datasets[0].data = data;
        balanceChart.update('none'); // 无动画更新
    } else {
        balanceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'USDT 余额',
                    data: data,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(0,0,0,0.05)'
                        }
                    }
                }
            }
        });
    }
}
