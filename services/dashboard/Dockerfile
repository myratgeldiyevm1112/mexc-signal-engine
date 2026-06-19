FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install poetry --break-system-packages && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --only main

RUN pip install fastapi uvicorn httpx --break-system-packages

COPY shared/ ./shared/
COPY services/dashboard/ ./services/dashboard/

CMD ["python", "-m", "services.dashboard.main"]