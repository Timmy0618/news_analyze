.PHONY: start stop api scrape embed migrate db help

# 啟動 API server（含排程器）
start:
	uv run python api_server.py

# 啟動本地 postgres（開發用，正式環境用 Supabase）
db:
	docker compose -f docker-compose-db.yml up -d
	@echo "Postgres: localhost:5432  pgAdmin: http://localhost:5050"

# 停止所有 docker 服務
stop:
	-docker compose -f docker-compose-db.yml down

# API 伺服器（含排程器）
api:
	uv run python api_server.py

# 手動執行爬蟲（可傳參數：make scrape PAGES=3 MAX=50 DATE=2026-05-12）
PAGES ?= 1
MAX   ?= 15
DATE  ?=
scrape:
	uv run python scripts/run_all_scrapers.py \
		--pages $(PAGES) \
		--max-articles $(MAX) \
		$(if $(DATE),--date $(DATE),)

# 生成嵌入向量
embed:
	uv run python scripts/generate_embeddings.py

# 執行資料庫 migration
migrate:
	uv run alembic upgrade head

help:
	@echo "make start      - 啟動 api server"
	@echo "make db         - 啟動本地 postgres + pgadmin"
	@echo "make stop       - 停止所有 docker 服務"
	@echo "make api        - 僅啟動 API server"
	@echo "make scrape     - 手動爬蟲 (PAGES=1 MAX=15 DATE=2026-05-12)"
	@echo "make embed      - 生成嵌入向量"
	@echo "make migrate    - 執行 alembic migrations"
