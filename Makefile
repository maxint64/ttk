.PHONY: help sync dev stop test check-js clean clean-data migrate seed rotate docker-up docker-down docker-reset docker-seed docker-rotate docker-smoke docker-perf

PYTHON := uv run python
VERBOSE_ARGS := $(if $(VERBOSE),-v,)
TEST_CMD := $(PYTHON) -m unittest discover $(VERBOSE_ARGS) -s server/tests -t .
DATE ?= $(shell date +%F)
ROTATE_ARGS := $(if $(DATE),--date $(DATE),)
SMOKE_DATE ?= $(shell date +%F)
SMOKE_URL ?= http://127.0.0.1:8000
PERF_ACTIVITIES ?= 1000
PERF_MIN_MEMBERS ?= 1
PERF_MAX_MEMBERS ?= 10
PERF_MIN_ROLES ?= 1
PERF_MAX_ROLES ?= 10
PERF_ROTATIONS ?= 100
PERF_READS ?= 1000
PERF_SKIPS ?= 100
PERF_BASE_DATE ?= $(shell date +%F)
PERF_RANDOM_SEED ?= 1
PERF_URL ?= http://127.0.0.1:8000

help:
	@printf "利用できるターゲット:\n"
	@printf "  make sync        Python依存関係をインストール/更新する\n"
	@printf "  make dev         ローカル開発サーバーを起動する\n"
	@printf "  make stop        ローカル開発サーバーを停止し、生成されたPythonファイルを削除する\n"
	@printf "  make test        バックエンドテストを実行し、生成されたPythonファイルを削除する。説明文を表示するには VERBOSE=1 を指定\n"
	@printf "  make check-js    フロントエンドJavaScriptの構文をチェックする\n"
	@printf "  make clean       生成されたPythonファイルを削除する\n"
	@printf "  make clean-data  ローカルSQLiteデータベースを削除する\n"
	@printf "  make migrate     ローカルSQLiteデータベースにAlembic migrationを適用する\n"
	@printf "  make seed        ローカルSQLiteデータベースを初期化し、テストデータを投入する\n"
	@printf "  make rotate      ローテーションを1回実行する。対象日はデフォルトで実行日、変えるには DATE=YYYY-MM-DD を指定\n"
	@printf "  make docker-up   Dockerサービスをビルドして起動する\n"
	@printf "  make docker-down Dockerサービスを停止する\n"
	@printf "  make docker-reset DockerのSQLiteデータベースを空に初期化する\n"
	@printf "  make docker-seed DockerのSQLiteデータベースを初期化し、テストデータを投入する\n"
	@printf "  make docker-rotate Docker Compose経由でローテーションを1回実行する。対象日はデフォルトで実行日、変えるには DATE=YYYY-MM-DD を指定\n"
	@printf "  make docker-smoke Dockerのseed/rotate/API応答を確認する。対象日はデフォルトで実行日、変えるには SMOKE_DATE=YYYY-MM-DD を指定\n"
	@printf "  make docker-perf Docker上で簡易性能試験を実行する。件数は PERF_* 変数で指定\n"

sync:
	uv sync

dev:
	$(PYTHON) -m server.run

stop:
	$(PYTHON) -m server.stop
	@$(MAKE) --no-print-directory clean

test:
	$(TEST_CMD)
	@$(MAKE) --no-print-directory clean

check-js:
	@for file in app/*.js; do node --check "$$file"; done

clean:
	@find server -type d -name __pycache__ -prune -exec rm -rf {} +
	@find server -type f -name "*.pyc" -delete
	@rm -rf .pytest_cache .mypy_cache .ruff_cache

clean-data:
	rm -rf data

migrate:
	$(PYTHON) -m alembic upgrade head

seed:
	$(PYTHON) -m server.db_tasks seed
	@$(MAKE) --no-print-directory clean

rotate:
	$(PYTHON) -m server.run_rotation $(ROTATE_ARGS)

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-reset:
	docker compose exec -T ttk uv run python -m server.db_tasks reset

docker-seed:
	docker compose run --rm ttk uv run python -m server.db_tasks seed

docker-rotate:
	docker compose run --rm ttk uv run python -m server.run_rotation $(ROTATE_ARGS)

docker-smoke:
	@set -eu; \
	cleanup() { $(MAKE) --no-print-directory docker-down; }; \
	trap cleanup EXIT; \
	$(MAKE) --no-print-directory docker-up; \
	$(MAKE) --no-print-directory docker-seed; \
	$(MAKE) --no-print-directory docker-rotate DATE=$(SMOKE_DATE); \
	$(PYTHON) -m server.docker_smoke --base-url $(SMOKE_URL) --date $(SMOKE_DATE)

docker-perf:
	@set -eu; \
	cleanup() { $(MAKE) --no-print-directory docker-down; }; \
	trap cleanup EXIT; \
	$(MAKE) --no-print-directory docker-up; \
	$(MAKE) --no-print-directory docker-reset; \
	docker compose exec -T ttk uv run python -m server.perf_smoke \
		--base-url $(PERF_URL) \
		--activities $(PERF_ACTIVITIES) \
		--min-members $(PERF_MIN_MEMBERS) \
		--max-members $(PERF_MAX_MEMBERS) \
		--min-roles $(PERF_MIN_ROLES) \
		--max-roles $(PERF_MAX_ROLES) \
		--rotations $(PERF_ROTATIONS) \
		--reads $(PERF_READS) \
		--skips $(PERF_SKIPS) \
		--base-date $(PERF_BASE_DATE) \
		--random-seed $(PERF_RANDOM_SEED)
