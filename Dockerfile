FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/
COPY src /app/src
RUN pip install --no-cache-dir .

ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python", "-m", "alfa_sync_bot"]
