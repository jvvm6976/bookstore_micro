FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary không cần gcc, bỏ apt-get đi
COPY requirements.txt .

# Install torch CPU-only first
RUN pip install --no-cache-dir \
    torch==2.3.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir faiss-cpu==1.8.0

COPY . .
RUN sed -i 's/\r//' entrypoint.sh && chmod +x entrypoint.sh
RUN mkdir -p artifacts data
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
