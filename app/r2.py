# app/r2.py
from __future__ import annotations

import os
from functools import lru_cache
from typing import BinaryIO, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError


class R2ConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _endpoint_url() -> str:
    account_id = os.getenv("R2_ACCOUNT_ID")
    if not account_id:
        raise R2ConfigError("R2_ACCOUNT_ID is not set")
    return f"https://{account_id}.r2.cloudflarestorage.com"


@lru_cache(maxsize=1)
def bucket_name() -> str:
    bucket = os.getenv("R2_BUCKET")
    if not bucket:
        raise R2ConfigError("R2_BUCKET is not set")
    return bucket


@lru_cache(maxsize=1)
def s3_client():
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise R2ConfigError("R2_ACCESS_KEY_ID or R2_SECRET_ACCESS_KEY is not set")

    # S3-compatible client for Cloudflare R2
    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=_endpoint_url(),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 5}),
    )


def upload_fileobj(
    fileobj: BinaryIO,
    key: str,
    content_type: Optional[str] = None,
    cache_control: Optional[str] = None,
) -> None:
    """
    Stream an object to R2.

    :param fileobj: file-like object opened in binary mode
    :param key: destination object key (e.g., 'uploads/2025/10/25/uuid-file.mp4')
    :param content_type: MIME type for the object
    :param cache_control: Optional Cache-Control header
    :raises: BotoCoreError/ClientError on failure
    """
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    if cache_control:
        extra_args["CacheControl"] = cache_control

    s3_client().upload_fileobj(fileobj, bucket_name(), key, ExtraArgs=extra_args)


def delete_object(key: str) -> None:
    """Delete an object from R2 (used later after processing)."""
    try:
        s3_client().delete_object(Bucket=bucket_name(), Key=key)
    except (BotoCoreError, ClientError):
        # Deletion failures shouldn't crash the request path for MVP.
        # Log later with Sentry; for now, swallow.
        pass
