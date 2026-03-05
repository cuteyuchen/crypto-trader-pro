FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 运行（使用 -m 以确保 src 包能被正确导入）
CMD ["python", "-m", "src.main"]
