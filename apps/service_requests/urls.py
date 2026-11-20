from django.urls import path

from .views import (
    ServiceRequestListView, ServiceRequestCreateView, ServiceRequestDetailView, ServiceRequestUpdateView,
    ServiceRequestUpdateMasterStatusView, ServiceRequestCompleteView, ServiceRequestCancelView, DeviceTypeListView,
    DeviceTypeCreateView, DeviceTypeDeleteView, ServiceRequestCopyView, ServiceRequestMainView, DeviceTypeUpdateView,
    ServiceRequestDiagnosticView, ServiceRequestCityAdminUpdateView, CreatedServiceRequestsView
)

app_name = 'service_request'

urlpatterns = [
    path('', ServiceRequestMainView.as_view(), name='request_main'),
    path('created/count/', CreatedServiceRequestsView.as_view(), name='created_count'),
    path('list/', ServiceRequestListView.as_view(), name='request_list'),
    path('create/', ServiceRequestCreateView.as_view(), name='request_create'),
    path('<int:pk>/', ServiceRequestDetailView.as_view(), name='request_detail'),
    path('<int:pk>/copy/', ServiceRequestCopyView.as_view(), name='request_copy'),
    path('<int:pk>/city_admin_update/', ServiceRequestCityAdminUpdateView.as_view(), name='request_city_admin_update'),
    path('<int:pk>/update/', ServiceRequestUpdateView.as_view(), name='request_update'),
    path('<int:pk>/update_master_status/', ServiceRequestUpdateMasterStatusView.as_view(), name='update_master_status'),
    path('<int:pk>/complete_request/', ServiceRequestCompleteView.as_view(), name='complete_request'),
    path('<int:pk>/diagnostic_request/', ServiceRequestDiagnosticView.as_view(), name='diagnostic_request'),
    path('<int:pk>/cancel_request/', ServiceRequestCancelView.as_view(), name='cancel_request'),

    path('device_type/', DeviceTypeListView.as_view(), name='device_type_list'),
    path('device_type/create/', DeviceTypeCreateView.as_view(), name='device_type_create'),
    path('device_type/<int:pk>/update/', DeviceTypeUpdateView.as_view(), name='device_type_update'),
    path('device_type/<int:pk>/delete/', DeviceTypeDeleteView.as_view(), name='device_type_delete'),
]
