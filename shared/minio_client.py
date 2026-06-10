from minio import Minio
from shared.config import settings


def get_minio_client() -> Minio:
    """Creates and returns a MinIO client."""
    return Minio(
        endpoint=f"{settings.minio_host}:{settings.minio_port}",
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )