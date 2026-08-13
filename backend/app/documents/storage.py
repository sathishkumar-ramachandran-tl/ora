"""GCS-backed object storage for the Document Vault. Thin wrapper around
google-cloud-storage — the routes/tests never touch the GCS client directly, so
swapping the backend later (or mocking it in tests) only touches this file.

Requires GCS_BUCKET_NAME (app config) and standard GCS credentials (typically
GOOGLE_APPLICATION_CREDENTIALS pointing at a service-account JSON key, or the
ambient credentials of the deployment environment) — the google-cloud-storage
client reads those itself; nothing GCS-specific is configured here.
"""
import uuid
from typing import BinaryIO

from flask import current_app


class StorageNotConfigured(Exception):
    """Raised when GCS_BUCKET_NAME isn't set — callers should surface this as a
    clean 400/503, not let a bucket-not-found GCS error leak through."""


def _bucket():
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import storage

    bucket_name = current_app.config.get('GCS_BUCKET_NAME')
    if not bucket_name:
        raise StorageNotConfigured(
            "GCS_BUCKET_NAME is not configured — set it (and GOOGLE_APPLICATION_CREDENTIALS) "
            "to enable Document Vault uploads."
        )
    try:
        client = storage.Client()
    except DefaultCredentialsError as e:
        raise StorageNotConfigured(
            "GCS_BUCKET_NAME or GCS credentials are not fully configured — set "
            "GCS_BUCKET_NAME and GOOGLE_APPLICATION_CREDENTIALS or deployment ambient "
            "credentials to enable Document Vault uploads."
        ) from e
    return client.bucket(bucket_name)


def upload_file(workspace_id: str, filename: str, file_stream: BinaryIO, content_type: str = None) -> str:
    """Streams file_stream to GCS under a workspace-scoped, collision-proof key.
    Returns the bucket_path to persist on the Document row."""
    bucket_path = f"vault/{workspace_id}/{uuid.uuid4()}_{filename}"
    blob = _bucket().blob(bucket_path)
    blob.upload_from_file(file_stream, content_type=content_type)
    return bucket_path


def generate_signed_url(bucket_path: str, expires_in_seconds: int = 300) -> str:
    """Short-lived signed URL for a direct-from-GCS download — avoids proxying
    file bytes through the Flask app."""
    from datetime import timedelta

    blob = _bucket().blob(bucket_path)
    return blob.generate_signed_url(expiration=timedelta(seconds=expires_in_seconds), method='GET')


def delete_file(bucket_path: str) -> None:
    from google.api_core.exceptions import NotFound

    blob = _bucket().blob(bucket_path)
    try:
        blob.delete()
    except NotFound:
        pass
