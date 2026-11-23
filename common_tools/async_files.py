import os
from contextlib import asynccontextmanager

import aiofiles
import aioboto3
import asynczipstream
from django.conf import settings
from django.core.files.storage import storages
from storages.backends.s3boto3 import S3Boto3Storage

S3_CHUNK_SIZE = 256 * 1024


@asynccontextmanager
async def storage_client():
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


async def s3_file_iterator(s3, filename):
    storage = storages['default']
    key = filename

    if storage.location:
        key = f'{storage.location}/{filename}'

    response = await s3.get_object(
        Bucket=storage.bucket_name,
        Key=key,
    )
    body = response['Body']

    try:
        while True:
            chunk = await body.read(S3_CHUNK_SIZE)

            if not chunk:
                break

            yield chunk
    finally:
        body.close()


async def local_file_iterator(filename):
    storage = storages['default']
    full_path = storage.path(filename)

    async with aiofiles.open(full_path, 'rb') as file:
        while True:
            chunk = await file.read(S3_CHUNK_SIZE)

            if not chunk:
                break

            yield chunk


async def storage_file_iterator(filename, s3=None):
    if s3 is not None:
        async for chunk in s3_file_iterator(s3, filename):
            yield chunk
    else:
        async for chunk in local_file_iterator(filename):
            yield chunk


async def generate_zip(files, s3=None):
    archive = asynczipstream.ZipFile(
        compression=asynczipstream.ZIP_DEFLATED,
    )

    async for item in files:
        archive_name = item.get('archive_name') or os.path.basename(item['name'])

        archive.write_iter(
            archive_name,
            storage_file_iterator(item['name'], s3),
        )

    async for chunk in archive:
        yield chunk
