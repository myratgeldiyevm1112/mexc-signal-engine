FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY services/analyzer/ ./services/analyzer/

CMD ["python", "-m", "services.analyzer.main"]
