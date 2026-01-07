# Dockerfile for ATLAS Canary Service
# This container runs synthetic agent traffic to continuously validate
# the ATLAS observability stack

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy canary package and runner
COPY canary/ ./canary/
COPY canary_runner.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command runs canary in a loop with 5-minute intervals
# Override with docker-compose command for different behavior
CMD ["sh", "-c", "while true; do python canary_runner.py --config canary/config_mock.yaml; sleep 300; done"]
