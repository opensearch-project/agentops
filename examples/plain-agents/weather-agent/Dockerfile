FROM python:3.12-slim

WORKDIR /app

# Copy application files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-instrumentation-asgi

# Expose port
EXPOSE 8000

# Run the server
CMD ["python", "server.py"]
