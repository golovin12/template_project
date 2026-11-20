from django.db import models


class USER_ROLES(models.TextChoices):
    MANAGER = 'manager', 'Генеральный Директор'
    CHIEF = 'chief', 'Директор филиала'
    CITY_ADMIN = 'city_admin', 'Администратор города'
