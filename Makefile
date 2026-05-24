.PHONY: help sync dev stop test check-js clean clean-data seed rotate docker-up docker-down docker-seed docker-rotate

PYTHON := uv run python
VERBOSE_ARGS := $(if $(VERBOSE),-v,)
TEST_CMD := $(PYTHON) -m unittest discover $(VERBOSE_ARGS) -s server/tests -t .
ROTATE_ARGS := $(if $(DATE),--date $(DATE),)

help:
	@printf "利用できるターゲット:\n"
	@printf "  make sync        Python依存関係をインストール/更新する\n"
	@printf "  make dev         ローカル開発サーバーを起動する\n"
	@printf "  make stop        ローカル開発サーバーを停止し、生成されたPythonファイルを削除する\n"
	@printf "  make test        バックエンドテストを実行し、生成されたPythonファイルを削除する。説明文を表示するには VERBOSE=1 を指定\n"
	@printf "  make check-js    フロントエンドJavaScriptの構文をチェックする\n"
	@printf "  make clean       生成されたPythonファイルを削除する\n"
	@printf "  make clean-data  ローカルSQLiteデータベースを削除する\n"
	@printf "  make seed        ローカルSQLiteデータベースを初期化し、テストデータを投入する\n"
	@printf "  make rotate      ローテーションを1回実行する。対象日を指定するには DATE=YYYY-MM-DD を指定\n"
	@printf "  make docker-up   Dockerサービスをビルドして起動する\n"
	@printf "  make docker-down Dockerサービスを停止する\n"
	@printf "  make docker-seed DockerのSQLiteデータベースを初期化し、テストデータを投入する\n"
	@printf "  make docker-rotate Docker Compose経由でローテーションを1回実行する。対象日を指定するには DATE=YYYY-MM-DD を指定\n"

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

seed:
	$(PYTHON) -m server.seed
	@$(MAKE) --no-print-directory clean

rotate:
	$(PYTHON) -m server.run_rotation $(ROTATE_ARGS)

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-seed:
	docker compose run --rm ttk uv run python -m server.seed

docker-rotate:
	docker compose run --rm ttk uv run python -m server.run_rotation $(ROTATE_ARGS)
