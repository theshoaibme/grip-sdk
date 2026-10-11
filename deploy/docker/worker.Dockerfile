FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || true

COPY . .
RUN pip install -e packages/grip-core -e packages/grip-python -e engine -e services/worker

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "services.worker.app.main"]
