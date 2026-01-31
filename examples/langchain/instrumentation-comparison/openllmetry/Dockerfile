FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY shared ./shared
COPY openllmetry/pyproject.toml .
COPY openllmetry/main.py .

RUN uv pip install --system .

CMD ["python", "main.py"]
