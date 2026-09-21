from functools import lru_cache
import boto3
from botocore.client import Config
from django.conf import settings


@lru_cache
def s3_client():
    scheme = "https" if settings.MINIO_SECURE else "http"
    return boto3.client("s3", endpoint_url=f"{scheme}://{settings.MINIO_ENDPOINT}",
                        aws_access_key_id=settings.MINIO_ACCESS_KEY,
                        aws_secret_access_key=settings.MINIO_SECRET_KEY,
                        config=Config(signature_version="s3v4"), region_name="us-east-1")


@lru_cache
def s3_public_client():
    """Client servant uniquement a signer des URL utilisables depuis le navigateur."""
    scheme = "https" if settings.MINIO_SECURE else "http"
    return boto3.client("s3", endpoint_url=f"{scheme}://{settings.MINIO_PUBLIC_ENDPOINT}",
                        aws_access_key_id=settings.MINIO_ACCESS_KEY,
                        aws_secret_access_key=settings.MINIO_SECRET_KEY,
                        config=Config(signature_version="s3v4"), region_name="us-east-1")


def ensure_buckets():
    client = s3_client()
    existing = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
    for bucket in (settings.MINIO_INPUT_BUCKET, settings.MINIO_REFERENCE_BUCKET, settings.MINIO_OUTPUT_BUCKET):
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)
