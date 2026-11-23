from django.db.models.signals import post_delete

from common_tools.signal import auto_delete_file_on_delete, add_field_name_kwargs
from .models import AccountingEntry

post_delete.connect(add_field_name_kwargs('receipt_photo')(auto_delete_file_on_delete), sender=AccountingEntry,
                    weak=False)
