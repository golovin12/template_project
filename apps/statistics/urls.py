from django.urls import path

from .views import CityStatisticsView, ClearStaticCacheView

app_name = 'statistics'

urlpatterns = [
    path('<int:pk>/', CityStatisticsView.as_view(), name='city_detail'),
    path('clear_cache/', ClearStaticCacheView.as_view(), name='clear_cache'),
]
