FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# tzdata：TZ=Asia/Taipei 需要 zoneinfo，slim image 預設沒有
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001 8501
