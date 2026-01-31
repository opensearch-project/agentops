FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    requests
# Langfuse is optional - install separately if needed
COPY main.py .
CMD ["python", "-u", "main.py"]
