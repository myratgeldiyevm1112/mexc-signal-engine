FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

ENV http_proxy=""
ENV https_proxy=""

COPY shared/ ./shared/
COPY services/collector/ ./services/collector/

CMD ["python", "-m", "services.collector.main"]