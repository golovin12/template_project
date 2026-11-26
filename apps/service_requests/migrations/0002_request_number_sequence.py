from django.db import migrations


SEQUENCE_NAME = 'service_requests_servicerequest_request_number_seq'
TABLE_NAME = 'service_requests_servicerequest'


def create_sequence(apps, schema_editor):
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT COALESCE(MAX(request_number), 100000) + 1 '
            f'FROM {connection.ops.quote_name(TABLE_NAME)}'
        )
        next_number = cursor.fetchone()[0]

        cursor.execute(
            f'CREATE SEQUENCE {SEQUENCE_NAME} START WITH {next_number}'
        )
        cursor.execute(
            f"ALTER TABLE {connection.ops.quote_name(TABLE_NAME)} "
            f"ALTER COLUMN request_number "
            f"SET DEFAULT nextval('{SEQUENCE_NAME}')"
        )


def drop_sequence(apps, schema_editor):
    table_name = schema_editor.connection.ops.quote_name(TABLE_NAME)

    schema_editor.execute(
        f'ALTER TABLE {table_name} ALTER COLUMN request_number DROP DEFAULT'
    )
    schema_editor.execute(f'DROP SEQUENCE IF EXISTS {SEQUENCE_NAME}')


class Migration(migrations.Migration):

    dependencies = [
        ('service_requests', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_sequence, drop_sequence),
    ]
