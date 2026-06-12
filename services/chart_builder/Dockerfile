FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY services/chart_builder/ ./services/chart_builder/

CMD ["python", "-m", "services.chart_builder.main"]
