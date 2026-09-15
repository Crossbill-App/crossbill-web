"""The one place the S3-or-local choice for book files is made.

A composition root that is not the DI container -- the SAQ worker, the Readium
backfill runner -- builds its file repository here, and the container's own
selector takes its S3 branch from here too.
"""

from typing import Any

import boto3

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.config import Settings
from src.infrastructure.library.repositories.file_repository import FileRepository
from src.infrastructure.library.repositories.s3_file_repository import S3FileRepository


def build_file_repository(settings: Settings) -> FileRepositoryProtocol:
    """Build the file repository this deployment is configured for."""
    if settings.s3_enabled:
        return build_s3_file_repository(settings)
    return FileRepository()


def build_s3_file_repository(settings: Settings) -> S3FileRepository:
    """Build the S3-backed store with a client for the configured bucket."""
    client: Any = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    return S3FileRepository(s3_client=client, bucket_name=settings.S3_BUCKET_NAME)  # type: ignore[arg-type]
