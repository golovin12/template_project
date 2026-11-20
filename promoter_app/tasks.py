from datetime import timedelta
from itertools import islice

from django.db.models import Q
from django.utils import timezone

from accounts.base import actor
from int.management.storage_backends import bulk_delete_media
from .models import PromoterAssignment, PromoterPhoto, RouteZone


@actor(queue_name='promotreck', time_limit=10 * 60 * 1000, max_age=40 * 60 * 1000)
def cleanup_old_promoter_assignment_photos():
    now = timezone.now()

    old_assignments_dt = now - timedelta(days=14)
    old_confirmed_dt = now - timedelta(days=2)

    assignments_qs = PromoterAssignment.objects.filter(
        Q(assigned_date__lte=old_assignments_dt) | Q(is_confirmed=True, confirmed_dt__lte=old_confirmed_dt)
    ).filter(is_cleaned=False)

    photo_iterator = PromoterPhoto.objects.filter(
        assignment__in=assignments_qs).values_list('id', 'image').iterator(chunk_size=1000)

    iterator = iter(photo_iterator)

    while chunk := list(islice(iterator, 500)):
        photo_ids = [photo_id for photo_id, _ in chunk]

        bulk_delete_media(image for _, image in chunk if image)

        PromoterPhoto.objects.filter(id__in=photo_ids)._raw_delete(PromoterPhoto.objects.db)

    assignments = list(assignments_qs.values('id', 'route_zone_id', 'status'))

    route_ids = {
        assignment['route_zone_id']
        for assignment in assignments
        if assignment['status'] != PromoterAssignment.Status.ENDED
    }

    if route_ids:
        RouteZone.objects.filter(id__in=route_ids).update(is_active=False)

    if assignments:
        PromoterAssignment.objects.filter(id__in=[assignment['id'] for assignment in assignments]).update(
            is_cleaned=True)
