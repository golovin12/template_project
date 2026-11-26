from pathlib import Path

from django.core import serializers
from django.db import migrations


def load_authuser_fixture(apps, schema_editor):
    AuthUser = apps.get_model('identity', 'AuthUser')
    database = schema_editor.connection.alias
    fixture_path = Path(__file__).resolve().parent.parent / 'fixtures' / 'identity.AuthUser.json'

    deserialized_objects = []

    with fixture_path.open(encoding='utf-8') as fixture:
        for deserialized_object in serializers.deserialize(
                'json', fixture, using=database, apps=apps, handle_forward_references=True
        ):
            if AuthUser.objects.using(database).filter(username__iexact=deserialized_object.object.username).exists():
                continue

            deserialized_object.save(using=database)

            if deserialized_object.deferred_fields:
                deserialized_objects.append(deserialized_object)

    for deserialized_object in deserialized_objects:
        deserialized_object.save_deferred_fields(using=database)


class Migration(migrations.Migration):
    dependencies = [
        ('identity', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_authuser_fixture, migrations.RunPython.noop),
    ]
