FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TTK_HOST=0.0.0.0 \
    TTK_PORT=8000 \
    TTK_DB_PATH=/app/data/ttk.sqlite3

WORKDIR /app

COPY . .

RUN python -m unittest discover -s tests

EXPOSE 8000

CMD ["python", "run.py"]
