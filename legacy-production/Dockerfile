FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /workspace

COPY app/requirements.txt /workspace/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /workspace/

CMD ["bash", "-c", "python -u app/sync_daemon.py & python -u app/tg_bot.py & wait -n"]
