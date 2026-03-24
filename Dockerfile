# openfox 服务镜像
FROM python:3.12-slim

WORKDIR /app

# 先复制依赖声明
COPY pyproject.toml uv.lock ./
RUN pip install -q uv

# 复制代码并安装（openfox 包需存在）
COPY . .
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# 使用 uv 安装后的环境运行
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 7777
