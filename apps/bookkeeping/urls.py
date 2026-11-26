from django.urls import path

from .views import DashboardView, AccountingEntryCreateView, AccountingEntryListView

app_name = 'bookkeeping'

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('', AccountingEntryListView.as_view(), name='entry_list'),
    path('create/', AccountingEntryCreateView.as_view(), name='entry_create'),
]
