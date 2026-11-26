import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterable, AsyncIterator, cast

import aiofiles
import aioboto3
import asynczipstream
from aiobotocore.response import StreamingBody
from storages.backends.s3boto3 import S3Boto3Storage
from types_aiobotocore_s3.client import S3Client

from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages

S3_CHUNK_SIZE = 256 * 1024


@dataclass(frozen=True, slots=True)
class ZipFileEntry:
    name: str
    archive_name: str


@asynccontextmanager
async def storage_client() -> AsyncIterator[S3Client | None]:
    storage = storages['default']

    if not isinstance(storage, S3Boto3Storage):
        yield None
        return

    session = aioboto3.Session()

    async with session.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', None),
    ) as s3:
        yield s3


async def s3_file_iterator(s3: S3Client, filename: str) -> AsyncIterator[bytes]:
    storage = cast(S3Boto3Storage, storages['default'])
    key = filename

    if storage.location:
        key = f'{storage.location}/{filename}'

    response = await s3.get_object(Bucket=storage.bucket_name, Key=key)
    body: StreamingBody = response['Body']

    try:
        while True:
            chunk = await body.read(S3_CHUNK_SIZE)

            if not chunk:
                break

            yield chunk
    finally:
        body.close()


async def local_file_iterator(filename: str) -> AsyncIterator[bytes]:
    storage = cast(FileSystemStorage, storages['default'])
    full_path = storage.path(filename)

    async with aiofiles.open(full_path, 'rb') as file:
        while True:
            chunk = await file.read(S3_CHUNK_SIZE)

            if not chunk:
                break

            yield chunk


async def storage_file_iterator(filename: str, s3: S3Client | None = None) -> AsyncIterator[bytes]:
    if s3 is not None:
        async for chunk in s3_file_iterator(s3, filename):
            yield chunk
    else:
        async for chunk in local_file_iterator(filename):
            yield chunk


async def generate_zip(files: AsyncIterable[ZipFileEntry], s3: S3Client | None = None) -> AsyncIterator[bytes]:
    archive = asynczipstream.ZipFile(compression=asynczipstream.ZIP_DEFLATED)

    async for item in files:
        archive_name = item.archive_name or os.path.basename(item.name)

        archive.write_iter(archive_name, storage_file_iterator(item.name, s3))

    async for chunk in archive:
        yield chunk
