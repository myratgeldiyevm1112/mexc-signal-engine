FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install poetry --break-system-packages && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --only main

COPY shared/ ./shared/
COPY services/watchdog/ ./services/watchdog/

CMD ["python", "-m", "services.watchdog.main"]