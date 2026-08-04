FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/model.json data/calibrated_model.pkl data/

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8003"]
