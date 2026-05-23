.PHONY: help sync dev build test clean clean-data rotate docker-up docker-down docker-rotate

PYTHON := uv run python
TEST_CMD := $(PYTHON) -m unittest discover -s server/tests -t .

help:
	@printf "Available targets:\n"
	@printf "  make sync        Install/update Python dependencies\n"
	@printf "  make dev         Start the local development server\n"
	@printf "  make build       Run the local build checks\n"
	@printf "  make test        Run backend tests, then remove generated Python files\n"
	@printf "  make clean       Remove generated Python files\n"
	@printf "  make clean-data  Remove the local SQLite database\n"
	@printf "  make rotate      Run rotation once\n"
	@printf "  make docker-up   Build and start Docker services\n"
	@printf "  make docker-down Stop Docker services\n"
	@printf "  make docker-rotate Run rotation once through Docker Compose\n"

sync:
	uv sync

dev:
	$(PYTHON) -m server.run

build: test

test:
	$(TEST_CMD)
	$(MAKE) clean

clean:
	find server -type d -name __pycache__ -prune -exec rm -rf {} +
	find server -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache

clean-data:
	rm -rf data

rotate:
	$(PYTHON) -m server.run_rotation

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-rotate:
	docker compose run --rm ttk uv run python -m server.run_rotation
