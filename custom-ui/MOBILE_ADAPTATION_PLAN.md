# 移动端适配技术方案

## 一、原版 UI 结构分析

基于 `src/dashboard/templates/index_v2.html` 分析:

### 1.1 导航结构
- 侧边栏导航 (240px 宽度)
- 6 个主要页面: Dashboard, Trades, Strategies, Backtest, Settings, Logs
- 当前活动页面高亮显示

### 1.2 页面布局
- 顶部标题栏 + 控制按钮
- 状态卡片网格
- 内容卡片容器
- 表格展示数据
- 图表可视化

### 1.3 交互方式
- Tab 切换 (Backtest 页面的配置/优化)
- 表单提交
- 按钮操作
- 实时数据刷新

---

## 二、移动端适配方案

### 2.1 导航简化 - 汉堡菜单

**设计目标**:
- 移除宽侧边栏，改为点击展开的汉堡菜单
- 保留核心页面: Dashboard, Trades, Strategies, Backtest
- 可选页面折叠: Logs, Settings

**实现方式**:
```html
<!-- mobile_navbar.html -->
<nav class="mobile-navbar">
  <div class="nav-header">
    <button class="hamburger">☰</button>
    <h1>Title</h1>
    <div class="status">Mode</div>
  </div>
  <div class="nav-dropdown">...</div>
</nav>
```

**关键技术点**:
- `position: fixed` 固定在顶部
- 使用 `max-height` + `transition` 实现平滑展开动画
- 汉堡图标变形动画 (CSS transform)

---

### 2.2 持仓表格 - 横向滚动

**设计目标**:
- 在移动端显示所有关键列
- 避免行高挤压导致内容换行
- 表头固定,便于识别列含义

**列选择**:
| 列名 | 宽度 | 说明 |
|------|------|------|
| 交易对 | 90px | 固定宽度,显示 Pair |
| 方向 | 60px | Buy/Sell 标签 |
| 数量 | 80px | 右对齐,显示精度 |
| 入场价 | 80px | 右对齐,价格显示 |
| **盈亏** | **80px** | **右对齐+颜色标记** |
| 操作 | 120px | 平仓/修改按钮 |

**实现代码**:
```css
.table-container {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}

.positions-table {
    min-width: 600px; /* 强制横向滚动 */
}

th {
    position: sticky;
    top: 0; /* 固定表头 */
}
```

**交互优化**:
- 点击行高亮反馈 (`tr:active`)
- 操作按钮足够大 (≥ 44px)
- 盈亏数字使用等宽字体方向

---

### 2.3 策略配置页 - 中文化 + 触摸优化

**设计目标**:
- 参数名称中文化
- 输入区域更大,便于触摸
- 分组显示,降低认知负担
- 实时验证反馈

**参数卡片设计**:
```html
<div class="param-item">
  <div class="param-header">
    <span class="param-name">快速均线周期</span>
  </div>
  <div class="param-desc">短周期均线,用于快速信号</div>
  <div class="param-inputs">
    <div class="param-input-group">
      <label>最小值</label>
      <input type="number" min="5" max="50">
    </div>
    <div class="param-input-group">
      <label>最大值</label>
      <input type="number" min="10" max="100">
    </div>
    <div class="param-input-group">
      <label>步进</label>
      <input type="number" min="1" max="10">
    </div>
  </div>
</div>
```

**触摸优化**:
- 输入框高度 ≥ 48px
- 网格布局 2 列显示范围输入
- 标签清晰,字号 ≥ 14px
- 错误提示使用颜色 + 文字

---

### 2.4 回测结果页 - 自适应图表

**设计目标**:
- Chart.js 图表宽度 100%
- 关键指标卡片网格显示
- 结果表格支持导出

**响应式图表**:
```css
.chart-container {
    height: 200px; /* 移动端适当减小高度 */
}

.chart-container canvas {
    width: 100% !important;
    height: 100% !important;
}
```

**统计网格**:
```css
.bt-stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr); /* 2 列显示 */
    gap: 12px;
}
```

---

## 三、核心 CSS 设计系统

### 3.1 CSS 变量
```css
:root {
    --primary: #667eea;        /* 主色调 */
    --success: #10b981;       /* 上涨/盈利 */
    --danger: #ef4444;        /* 下跌/亏损 */
    --bg: #f5f7fa;           /* 背景色 */
    --card: #ffffff;         /* 卡片背景 */
    --text: #333333;         /* 主文字 */
    --touch-min: 44px;       /* 最小触摸尺寸 */
    --radius: 12px;          /* 圆角 */
    --spacing: 16px;         /* 基础间距 */
}
```

### 3.2 触摸尺寸规范
所有交互元素必须遵循:
- 最小高度: `44px`
- 最小宽度: `44px` (或 满宽)
- 内边距: `10px 20px`
- 行间距: `≥ 12px`

### 3.3 响应式断点
```
移动端: < 768px (默认样式)
平板:   ≥ 768px (使用平板样式)
桌面:   ≥ 1024px (可恢复侧边栏)
```

---

## 四、关键交互实现

### 4.1 汉堡菜单
```javascript
const hamburger = document.getElementById('hamburger-btn');
const dropdown = document.getElementById('nav-dropdown');

hamburger.addEventListener('click', () => {
  dropdown.classList.toggle('show');
  hamburger.classList.toggle('active');
});
```

### 4.2 模态框
```javascript
// 打开
fab.addEventListener('click', () => {
  modal.classList.add('show');
});

// 关闭
closeBtn.addEventListener('click', () => {
  modal.classList.remove('show');
});

// 点击遮罩关闭
overlay.addEventListener('click', () => {
  modal.classList.remove('show');
});
```

### 4.3 底部导航 (可选)
```html
<nav class="bottom-nav">
  <a href="#" class="bottom-nav-item active">
    <span class="bottom-nav-icon">📊</span>
    <span>概览</span>
  </a>
  ...
</nav>
```

---

## 五、性能优化

### 5.1 CSS 压缩
使用 CSSNano 或在线工具压缩 `mobile.css`

### 5.2 图片懒加载
图表初始不加载,页面可见时再渲染

### 5.3 防抖刷新
数据刷新使用 3-5 秒防抖,避免频繁请求

---

## 六、浏览器兼容性

| 浏览器 | 支持版本 |
|--------|----------|
| iOS Safari | 12+ ✓ |
| Chrome Android | 70+ ✓ |
| Samsung Internet | 10+ ✓ |
| Firefox Android | 65+ ✓ |
| Android Browser | 8+ ⚠️ |

**Polyfill 需求**:
- CSS Grid (旧浏览器)
- `env(safe-area-inset-bottom)`

---

## 七、交付物清单

### ✅ mobile_navbar.html
- 固定顶部导航
- 汉堡菜单按钮
- 下拉导航项
- 状态徽章
- 移动端最优高度

### ✅ trades_mobile.html
- 统计卡片网格
- 横向滚动表格
- 快速下单 FAB
- 模态下单表单
- 买入/卖出切换
- 空状态/加载状态

### ✅ mobile.css
- 完整设计系统
- 响应式网格
- 触摸优化组件
- 暗色模式支持
- 安全区域适配
- 打印样式

---

## 八、下一步工作

1. **JavaScript 实现**
   - 数据加载与渲染
   - 表格排序/筛选
   - 图表初始化
   - API 错误处理

2. **测试**
   - 真机测试 (iOS/Android)
   - 不同屏幕尺寸
   - 网络慢速场景
   - 触摸手势测试

3. **性能优化**
   - 图片压缩
   - CSS/JS 压缩合并
   - 懒加载实现

4. **部署**
   - 修改 Flask 模板路径
   - 配置静态文件缓存
   - 添加 Analytics

---

## 九、参考文档

- [Apple HIG - Touch Targets](https://developer.apple.com/design/human-interface-guidelines/ios/visual-design/adaptivity-and-layout/)
- [Google Material Design - Components](https://material.io/components)
- [CSS Tricks - Media Queries](https://css-tricks.com/snippets/css/media-queries-for-standard-devices/)

---

**设计日期**: 2025-03-05
**设计师**: 小螃蟹 🦀
**版本**: v1.0
