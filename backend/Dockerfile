# 基于轻量级 Python 3.11 镜像
FROM python:3.11-slim

WORKDIR /app

# 设置环境变量，防止 Python 缓冲输出
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIRECTORY=/app/data/processed \
    CATALOG_DATABASE=/app/data/processed/catalog.sqlite3 \
    KNOWLEDGE_SOURCE=/app/data/knowledge/rules.json \
    USAGE_REPORT=/app/data/processed/usage.json

# 安装系统基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装
# RAG/ML 重依赖（torch + CUDA，数 GB）默认不装，需要时：
#   docker build --build-arg INSTALL_ML=true -t xiaojia-backend ./backend
COPY backend/requirements*.txt ./
ARG INSTALL_ML=false
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi

# 复制后端源码
COPY backend/app ./app
# 只复制标准库运行模块与公开规则摘要，原始数据不进入镜像。
COPY data/*.py ./data/
COPY data/knowledge ./data/knowledge/

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
