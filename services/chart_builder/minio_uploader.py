"""
services/chart_builder/minio_uploader.py
Uploads chart PNG bytes to MinIO and returns a URL.
"""

import io
from datetime import datetime, timezone

from minio import Minio
from loguru import logger

from shared.config import settings


def get_minio_client() -> Minio:
    return Minio(
        f"{settings.minio_host}:{settings.minio_port}",
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(client: Minio) -> None:
    bucket = settings.minio_bucket_charts
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info(f"Created MinIO bucket: {bucket}")


def upload_chart(client: Minio, symbol: str, png_bytes: bytes) -> str:
    """
    Uploads PNG bytes to MinIO under charts/{date}/{symbol}_{timestamp}.png
    Returns the object URL (path-style).
    """
    bucket = settings.minio_bucket_charts
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    ts = int(now.timestamp())
    object_name = f"{date_str}/{symbol}_{ts}.png"

    data = io.BytesIO(png_bytes)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=data,
        length=len(png_bytes),
        content_type="image/png",
    )

    scheme = "https" if settings.minio_secure else "http"
    url = f"{scheme}://{settings.minio_host}:{settings.minio_port}/{bucket}/{object_name}"
    logger.debug(f"Uploaded chart to MinIO: {url}")
    return url