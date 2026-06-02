FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    libpq-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_DEFAULT_TIMEOUT=300

# 1. PyTorch CPU-only (primary — LSTM model)
RUN pip install --no-cache-dir \
    torch==2.3.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# 2. Core requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. FAISS for RAG retrieval
RUN pip install --no-cache-dir faiss-cpu==1.8.0 || echo "faiss-cpu optional, skipping"

COPY . .
RUN chmod +x entrypoint.sh
RUN mkdir -p artifacts data

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
