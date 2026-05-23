FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TTK_HOST=0.0.0.0 \
    TTK_PORT=8000 \
    TTK_DB_PATH=/app/data/ttk.sqlite3

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.5.29 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

RUN uv run python -m unittest discover -s server/tests -t .

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "server.run"]
