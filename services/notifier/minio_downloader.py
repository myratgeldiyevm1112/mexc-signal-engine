"""
services/notifier/minio_downloader.py
Downloads chart PNG bytes from MinIO given the stored chart_url.
"""

from urllib.parse import urlparse

from minio import Minio

from shared.config import settings


def get_minio_client() -> Minio:
    return Minio(
        f"{settings.minio_host}:{settings.minio_port}",
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def download_chart(client: Minio, chart_url: str) -> bytes:
    """
    chart_url looks like: http://minio:9000/charts/2026-06-12/BTCUSDT_123.png
    Extracts bucket + object name and downloads the bytes.
    """
    path = urlparse(chart_url).path.lstrip("/")
    bucket, _, object_name = path.partition("/")

    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()