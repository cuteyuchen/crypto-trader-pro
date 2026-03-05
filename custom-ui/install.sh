#!/bin/bash
# 移动端 UI 安装脚本
# 使用方法: ./install.sh [项目路径]

set -e

PROJECT_PATH="${1:-/home/admin/.openclaw/workspace/PROJECTS/crypto-trader-pro}"
SOURCE_PATH="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 开始安装移动端 UI..."
echo "📁 项目路径: $PROJECT_PATH"
echo "📦 源文件路径: $SOURCE_PATH"

# 检查目标目录
if [ ! -d "$PROJECT_PATH/src/dashboard/templates" ]; then
    echo "❌ 错误: 找不到目标目录"
    echo "   请确认路径: $PROJECT_PATH/src/dashboard/templates"
    exit 1
fi

# 复制 HTML 模板
echo "📋 复制 HTML 模板..."
cp "$SOURCE_PATH/mobile_navbar.html" "$PROJECT_PATH/src/dashboard/templates/"
cp "$SOURCE_PATH/trades_mobile.html" "$PROJECT_PATH/src/dashboard/templates/"

# 复制静态资源
echo "🎨 复制 CSS 样式..."
cp -r "$SOURCE_PATH/static" "$PROJECT_PATH/src/dashboard/"

# 检查 app_v2.html 或 index_v2.html
if [ -f "$PROJECT_PATH/src/dashboard/templates/index_v2.html" ]; then
    echo "🔧 检测到 index_v2.html"
    # 提示用户手动修改
elif [ -f "$PROJECT_PATH/src/dashboard/templates/app.html" ]; then
    echo "🔧 检测到 app.html"
fi

echo ""
echo "✅ 安装完成！"
echo ""
echo "📝 后续步骤:"
echo "1. 在主模板中引入 mobile.css:"
echo "   <link rel=\"stylesheet\" href=\"/static/css/mobile.css\">"
echo ""
echo "2. 替换侧边栏为移动端导航:"
echo "   {% include 'mobile_navbar.html' %}"
echo ""
echo "3. 参考 README.md 进行集成"
echo ""
echo "📖 更多信息请查看:"
echo "   - README.md (使用指南)"
echo "   - MOBILE_ADAPTATION_PLAN.md (技术方案)"
echo ""
