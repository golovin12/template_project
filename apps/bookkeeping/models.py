from decimal import Decimal

from django.db import models
from django.db.models import Sum, Case, When, F, Value, DecimalField, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from common_tools.validators import validate_file_field


class AccountingEntry(models.Model):
    class ENTRY_TYPE:
        INCOME = 'income'
        EXPENSE = 'expense'

        CHOICES = (
            (INCOME, 'Доходы'),
            (EXPENSE, 'Расходы'),
        )

    class EXPENSE_SUBTYPE:
        MASTER = 'master'
        PROMO = 'promo'
        STAFF = 'staff'
        OTHER = 'other'

        CHOICES = (
            (MASTER, 'ЗП мастеру'),
            (PROMO, 'ЗП промо'),
            (STAFF, 'ЗП сотруднику'),
            (OTHER, 'Прочее'),
        )

    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE.CHOICES, verbose_name='Тип')
    expense_subtype = models.CharField(verbose_name='Вид расходов', choices=EXPENSE_SUBTYPE.CHOICES, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Сумма (руб.)')
    description = models.TextField(verbose_name='Описание')
    branch = models.ForeignKey('accounts.Branch', on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name='Филиал')
    city = models.ForeignKey('accounts.City', on_delete=models.SET_NULL, null=True, verbose_name='Город')
    created_dt = models.DateTimeField(default=timezone.now, verbose_name='Время добавления')
    service_request = models.ForeignKey('service_requests.ServiceRequest', on_delete=models.SET_NULL, null=True,
                                        blank=True, verbose_name='Связанная заявка')
    receipt_photo = models.ImageField(verbose_name='Фото чека', max_length=200, validators=[validate_file_field],
                                      upload_to='bookkeeping/models.AccountingEntry.receipt_photo', null=True,
                                      blank=True)
    created_by = models.ForeignKey('accounts.OrganizationUser', on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='Кем создана')

    class Meta:
        verbose_name = 'Бухгалтерия'
        verbose_name_plural = 'Бухгалтерия'
        indexes = (
            models.Index(fields=('city',), name='idx_income_city', condition=Q(entry_type='income')),
            models.Index(fields=('city',), name='idx_expense_city', condition=Q(entry_type='expense')),
            models.Index(fields=('branch', 'created_dt'), name='idx_branch_created')
        )
        ordering = ('-created_dt',)

    def __str__(self):
        return f'{self.get_entry_type_display()} - {self.amount} руб. ' \
               f'({self.branch or self.city}): {self.description[:50]}'

    def save(self, *args, **kwargs):
        if self.branch:
            self.city_id = self.branch.city_id
        super().save(*args, **kwargs)

    @classmethod
    def get_city_balance(cls, city_id: int) -> Decimal:
        qs = cls.objects.filter(city_id=city_id)

        agg = qs.aggregate(
            income=Coalesce(
                Sum(Case(
                    When(entry_type='income', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField()
                )),
                Value(0, output_field=DecimalField())
            ),
            expense=Coalesce(
                Sum(Case(
                    When(entry_type='expense', then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField()
                )),
                Value(0, output_field=DecimalField())
            ),
        )
        return agg['income'] - agg['expense']
