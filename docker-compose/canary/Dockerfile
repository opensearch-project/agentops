FROM python:3.12-slim

WORKDIR /app

# Install requests library
RUN pip install --no-cache-dir requests

# Copy canary script
COPY canary.py .

# Run the canary
CMD ["python", "canary.py"]
