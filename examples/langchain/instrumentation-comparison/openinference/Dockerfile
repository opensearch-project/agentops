FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY shared ./shared
COPY openinference/pyproject.toml .
COPY openinference/main.py .

RUN uv pip install --system .

CMD ["python", "main.py"]
