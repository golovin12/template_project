from django_select2.forms import Select2Widget

from django import forms

from accounts.form import BranchControlMixin
from common_tools.form import WithoutPlaceholderMixin
from .models import AccountingEntry


class AccountingEntryForm(BranchControlMixin, WithoutPlaceholderMixin, forms.ModelForm):
    class Meta:
        model = AccountingEntry
        fields = ('entry_type', 'amount', 'description', 'branch', 'receipt_photo')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'entry_type': Select2Widget(attrs={'style': 'opacity: 0'}),
        }

    def __init__(self, *args, **kwargs):
        self.mode = kwargs.pop('mode', None)
        super().__init__(*args, **kwargs)

        self.instance.created_by = self.request.user.organization_user

        if self.mode == AccountingEntry.ENTRY_TYPE.INCOME:
            self._setup_income()
        elif self.mode == AccountingEntry.ENTRY_TYPE.EXPENSE:
            self._setup_expense()

    def _setup_income(self):
        self.fields['entry_type'].initial = AccountingEntry.ENTRY_TYPE.INCOME
        self.fields['entry_type'].disabled = True

    def _setup_expense(self):
        self.fields['entry_type'].initial = AccountingEntry.ENTRY_TYPE.EXPENSE
        self.fields['entry_type'].disabled = True
        self.instance.expense_subtype = AccountingEntry.EXPENSE_SUBTYPE.OTHER
