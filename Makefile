.PHONY: help sync dev stop test clean clean-data seed rotate docker-up docker-down docker-rotate

PYTHON := uv run python
TEST_CMD := $(PYTHON) -m unittest discover -s server/tests -t .
ROTATE_ARGS := $(if $(DATE),--date $(DATE),)

help:
	@printf "Available targets:\n"
	@printf "  make sync        Install/update Python dependencies\n"
	@printf "  make dev         Start the local development server\n"
	@printf "  make stop        Stop the local development server, then remove generated Python files\n"
	@printf "  make test        Run backend tests, then remove generated Python files\n"
	@printf "  make clean       Remove generated Python files\n"
	@printf "  make clean-data  Remove the local SQLite database\n"
	@printf "  make seed        Reset the local SQLite database and insert test data\n"
	@printf "  make rotate      Run rotation once. Use DATE=YYYY-MM-DD to target a date\n"
	@printf "  make docker-up   Build and start Docker services\n"
	@printf "  make docker-down Stop Docker services\n"
	@printf "  make docker-rotate Run rotation once through Docker Compose. Use DATE=YYYY-MM-DD to target a date\n"

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
	docker compose up --build

docker-down:
	docker compose down

docker-rotate:
	docker compose run --rm ttk uv run python -m server.run_rotation $(ROTATE_ARGS)
