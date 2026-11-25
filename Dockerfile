FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY configs/ ./configs/
COPY data/ ./data/
COPY src/ ./src/

CMD ["python3", "-m", "eval_worker.cli", "benchmark", "--enforce-gate"]
