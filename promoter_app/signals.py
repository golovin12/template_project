from django.db.models.signals import post_delete

from common_tools.signal import auto_delete_file_on_delete, add_field_name_kwargs
from promoter_app.models import PromoterPhoto

post_delete.connect(add_field_name_kwargs('image')(auto_delete_file_on_delete), sender=PromoterPhoto, weak=False)
