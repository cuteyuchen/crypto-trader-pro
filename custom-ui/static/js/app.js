// Crypto Trader Pro - 移动端 UI 交互库

document.addEventListener('DOMContentLoaded', function() {
    // 汉堡菜单切换
    const hamburger = document.getElementById('hamburger-btn');
    const dropdown = document.getElementById('nav-dropdown');
    if (hamburger && dropdown) {
        hamburger.addEventListener('click', function() {
            dropdown.classList.toggle('show');
            hamburger.classList.toggle('active');
        });

        // 点击菜单项后关闭
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                dropdown.classList.remove('show');
                hamburger.classList.remove('active');
            });
        });
    }

    // 快速下单按钮（ trades 页面）
    const fab = document.getElementById('quick-order-fab');
    const orderModal = document.getElementById('order-modal');
    if (fab && orderModal) {
        fab.addEventListener('click', () => {
            orderModal.classList.add('show');
        });
        document.getElementById('close-order-modal').addEventListener('click', () => {
            orderModal.classList.remove('show');
        });
        document.querySelector('.modal-overlay')?.addEventListener('click', () => {
            orderModal.classList.remove('show');
        });
    }
});

// 全局 API 调用辅助函数
const API_BASE = '';

async function fetchJSON(url, options = {}) {
    const res = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });
    return res.json();
}

// 显示 Toast 消息
function showToast(message, type = 'info') {
    // 简单实现，可替换为更美观的组件
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.background = type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#333';
    toast.style.color = 'white';
    toast.style.padding = '10px 20px';
    toast.style.borderRadius = '8px';
    toast.style.zIndex = '9999';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
