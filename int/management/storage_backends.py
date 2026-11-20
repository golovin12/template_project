from itertools import islice

from storages.backends.s3boto3 import S3Boto3Storage
from storages.utils import clean_name

from django.core.files.storage import FileSystemStorage, storages


class DevMediaStorage(FileSystemStorage):

    def direct_url(self, name, expire=3600):
        return self.url(name)


class MediaStorage(S3Boto3Storage):
    """Хранилище медиа"""
    bucket_name = '091a0cc3-02303de7-8ec4-40c3-a350-3d5f8431bec4'
    location = 'media'
    default_acl = 'private'
    file_overwrite = False

    def direct_url(self, name, expire=3600):
        name = self._normalize_name(clean_name(name))

        return self.connection.meta.client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': name,
            },
            ExpiresIn=expire,
        )


class BackupStorage(S3Boto3Storage):
    """Хранилище бэкапов"""
    bucket_name = '091a0cc3-02303de7-8ec4-40c3-a350-3d5f8431bec4'
    location = 'backups'
    default_acl = 'private'
    file_overwrite = True


def bulk_delete_media(file_names, chunk_size=500):
    storage = storages['default']

    iterator = iter(file_names)

    if isinstance(storage, S3Boto3Storage):
        while chunk := list(islice(iterator, chunk_size)):
            storage.connection.meta.client.delete_objects(
                Bucket=storage.bucket_name,
                Delete={
                    'Objects': [{'Key': f'{storage.location}/{name}'} for name in chunk],
                    'Quiet': True,
                },
            )
    else:
        for file_name in iterator:
            storage.delete(file_name)
