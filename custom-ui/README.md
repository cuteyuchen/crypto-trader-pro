# 移动端 UI 适配方案 - Crypto Trader Pro

基于 freqtrade 原版 WebUI 设计的移动端优先界面

## 📦 交付物清单

- ✅ `mobile_navbar.html` - 移动端导航栏（汉堡菜单）
- ✅ `trades_mobile.html` - 移动端持仓页面
- ✅ `static/css/mobile.css` - 移动端样式库

## 🎯 设计原则

1. **移动端优先** - 触摸优化，按钮 ≥44px
2. **性能优先** - 轻量级，快速加载
3. **清晰易读** - 大字体，高对比度
4. **一致性** - 保持原版品牌风格

## 📱 核心特性

### 1. 简化导航 (汉堡菜单)
```
- 折叠式导航栏，点击汉堡按钮展开
- 核心页面：概览 / 交易 / 策略 / 回测
- 可选页面：日志 / 设置 (默认隐藏)
- 图标 + 文字，清晰识别
- 支持底部导航栏 (可选)
```

### 2. 持仓表格优化
```
- 横向滚动，避免挤压
- 关键列：交易对 | 方向 | 数量 | 入场价 | 盈亏 | 操作
- 固定表头，滚动时保持可见
- 盈亏颜色标记 (红跌绿涨)
- 快速操作按钮：平仓 / 修改
```

### 3. 策略配置页
```
- 参数表单中文化
- 触摸优化的大按钮
- 分组显示参数类别
- 实时验证输入
- 下拉选择代替复杂配置
```

### 4. 回测结果页
```
- 图表自适应宽度
- 关键指标卡片网格
-  Pull-to-refresh 支持
- 结果导出 CSV
```

### 5. 触摸优化
```
- 所有按钮 ≥ 44px × 44px
- 间距 ≥ 12px
- 字体 ≥ 16px (正文)
- 表单输入框高度 ≥ 48px
- 避免 hover-only 交互
```

## 🛠️ 集成步骤

### 步骤 1: 复制文件到项目
```bash
# 复制 HTML 模板
cp custom-ui/mobile_navbar.html PROJECTS/crypto-trader-pro/src/dashboard/templates/
cp custom-ui/trades_mobile.html PROJECTS/crypto-trader-pro/src/dashboard/templates/

# 复制 CSS
cp -r custom-ui/static PROJECTS/crypto-trader-pro/src/dashboard/
```

### 步骤 2: 修改主模板
在 `index_v2.html` 或主模板中引入移动端样式:

```html
<link rel="stylesheet" href="/static/css/mobile.css">
```

### 步骤 3: 使用移动端导航
替换原有的侧边栏导航为 `mobile_navbar.html`:

```html
<!-- 在 main 标签前插入 -->
{% include "mobile_navbar.html" %}

<!-- 隐藏原有侧边栏 -->
<style>
.sidebar { display: none; }
</style>
```

### 步骤 4: 集成持仓页面
在交易/持仓页面使用 `trades_mobile.html` 的结构:

```html
<div class="mobile-page" id="trades-page">
    <!-- 复制 trades_mobile.html 内容 -->
</div>
```

### 步骤 5: 添加 JavaScript 交互
创建 `static/js/mobile.js` 处理交互:

```javascript
// 汉堡菜单
document.getElementById('hamburger-btn').addEventListener('click', function() {
    document.getElementById('nav-dropdown').classList.toggle('show');
    this.classList.toggle('active');
});

// 导航切换
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', function(e) {
        e.preventDefault();
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
        // 切换页面逻辑...
        document.getElementById('nav-dropdown').classList.remove('show');
        document.getElementById('hamburger-btn').classList.remove('active');
    });
});

// 模态框控制
document.getElementById('quick-order-fab').addEventListener('click', function() {
    document.getElementById('order-modal').classList.add('show');
});

document.getElementById('close-order-modal').addEventListener('click', function() {
    document.getElementById('order-modal').classList.remove('show');
});

// 点击遮罩关闭
document.querySelector('.modal-overlay').addEventListener('click', function() {
    document.getElementById('order-modal').classList.remove('show');
});

// 买入/卖出按钮切换
document.querySelectorAll('.btn-side').forEach(btn => {
    btn.addEventListener('click', function() {
        document.querySelectorAll('.btn-side').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
    });
});

// 快速下单提交
document.getElementById('quick-order-form').addEventListener('submit', function(e) {
    e.preventDefault();
    // 发送 API 请求...
});
```

## 🎨 样式定制

### 修改主题色
在 CSS 开头修改 `:root` 变量:

```css
:root {
    --primary: #667eea;      /* 主色调 */
    --success: #10b981;      /* 盈利/上涨 */
    --danger: #ef4444;       /* 亏损/下跌 */
    --bg: #f5f7fa;          /* 背景色 */
}
```

### 暗色模式
CSS 已内置 `prefers-color-scheme: dark` 支持，自动适配系统设置。

## 📏 设计规格

| 元素 | 规格 | 说明 |
|------|------|------|
| 按钮高度 | ≥ 44px | 苹果人机指南标准 |
| 间距 | 16px | 统一间距系统 |
| 字体大小 | 16px | 正文最小可读尺寸 |
| 表格最小宽度 | 600px | 需要横向滚动 |
| 圆角 | 8-12px | 亲和力设计 |
| 阴影 | 柔和 | 提升层次感 |

## 🧪 测试清单

- [ ] 汉堡菜单展开/收起正常
- [ ] 所有按钮可触摸（≥44px）
- [ ] 表格横向滚动流畅
- [ ] 盈亏颜色正确显示
- [ ] 快速下单表单提交正常
- [ ] 模态框遮罩点击关闭
- [ ] 暗色模式切换正常
- [ ] iPhone 安全区域适配
- [ ] 网络慢时加载状态显示

## 📱 推荐浏览器

- ✅ iOS Safari 12+
- ✅ Chrome for Android
- ✅ Samsung Internet
- ✅ Firefox for Android

## 🐛 已知问题

1. 表格列较多时，可能需要用户左右滚动体验欠佳
   **解决方案**: 考虑将部分次要列放入详情页

2. 图表在小屏幕上高度有限
   **解决方案**: 保持图表高度 200-250px，确保可读性

3. 部分旧设备可能不支持 CSS Grid
   **解决方案**: 已提供 flex 回退方案

## 📚 参考资源

- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines)
- [Google Material Design](https://material.io/design)
- [CSS Tricks - Mobile First](https://css-tricks.com/mobile-first-css/)

---

**版本**: 1.0.0
**最后更新**: 2025-03-05
**维护者**: 小螃蟹 (Xiao Pangxie) 🦀
