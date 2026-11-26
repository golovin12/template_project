from django.db import migrations, models
from django.db.models.expressions import RawSQL


SEQUENCE_NAME = 'service_requests_servicerequest_request_number_seq'
TABLE_NAME = 'service_requests_servicerequest'


def create_sequence(apps, schema_editor):
    connection = schema_editor.connection
    table_name = connection.ops.quote_name(TABLE_NAME)
    sequence_name = connection.ops.quote_name(SEQUENCE_NAME)

    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT COALESCE(MAX(request_number), 100000) + 1 FROM {table_name}'
        )
        next_number = cursor.fetchone()[0]

        cursor.execute(f'CREATE SEQUENCE {sequence_name} START WITH {next_number}')
        cursor.execute(
            f'ALTER SEQUENCE {sequence_name} OWNED BY {table_name}.request_number'
        )


def drop_sequence(apps, schema_editor):
    sequence_name = schema_editor.connection.ops.quote_name(SEQUENCE_NAME)
    schema_editor.execute(f'DROP SEQUENCE IF EXISTS {sequence_name}')


class Migration(migrations.Migration):

    dependencies = [
        ('service_requests', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_sequence, drop_sequence),
        migrations.AlterField(
            model_name='servicerequest',
            name='request_number',
            field=models.PositiveIntegerField(
                unique=True,
                verbose_name='Номер заявки',
                editable=False,
                db_default=RawSQL(
                    "nextval('service_requests_servicerequest_request_number_seq'::regclass)",
                    [],
                ),
            ),
        ),
    ]
