from django.urls import path

from .views import (
    AppDashboardView, RoutesEditorView, SaveRoutesApiView, RoutesAssignView, AssignPromoRouteApiView,
    AssignmentsListView, AssignmentDetailView, PromoterQrView, PromoterLogoutView, PromoterCreateView,
    PromotersListView, PromoterUpdateView, PromoterDeleteView, AssignmentConfirmView, MainPageView, PrivacyPolicyView,
    TermsOfServiceView, AppVersionsSettingsView, AssignmentCancelView
)
from .app_views import AssignmentUploadAPIView, MyAssignmentsApiView, AuthCheckApiView, VersionCheckApiView
from .photo_zip import DownloadAssignmentPhotosView

app_name = 'promoter_app'

urlpatterns = [
    # Общедоступная информация
    path('', MainPageView.as_view(), name='main_page'),
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('terms-of-service/', TermsOfServiceView.as_view(), name='terms_of_service'),
    # Внутренние ссылки
    path('dashboard/', AppDashboardView.as_view(), name='dashboard'),
    path('city/routes/', RoutesEditorView.as_view(), name='routes_editor'),
    path('city/routes/assign/', RoutesAssignView.as_view(), name='routes_assign'),
    path('city/assignments/', AssignmentsListView.as_view(), name='assignments'),
    path('assignment/<int:pk>/', AssignmentDetailView.as_view(), name='assignment_detail'),
    path('assignment/<int:pk>/photos/', DownloadAssignmentPhotosView.as_view(), name='download_assignment_photos'),

    path('api/city/routes/save/', SaveRoutesApiView.as_view(), name='save_routes_api'),
    path('api/assign-promo-route/', AssignPromoRouteApiView.as_view(), name='assign_promo_route_api'),
    path('api/assignment/<int:pk>/confirm/', AssignmentConfirmView.as_view(), name='assignment_confirm_api'),
    path('api/assignment/<int:pk>/cancel/', AssignmentCancelView.as_view(), name='assignment_cancel_api'),

    path('city/promoters/', PromotersListView.as_view(), name='promoters_list'),
    path('city/promoters/create/', PromoterCreateView.as_view(), name='promoter_create'),
    path('promoter/<int:pk>/edit/', PromoterUpdateView.as_view(), name='promoter_edit'),
    path('promoter/<int:pk>/delete/', PromoterDeleteView.as_view(), name='promoter_delete'),
    path('promoter/<int:pk>/logout/', PromoterLogoutView.as_view(), name='promoter_logout'),
    path('promoter/<int:pk>/qr/', PromoterQrView.as_view(), name='promoter_qr'),

    path('app_versions/', AppVersionsSettingsView.as_view(), name='app_versions'),

    # Api приложения
    path('api/version/check/', VersionCheckApiView.as_view(), name='version_check_api'),
    path('/api/version/check/', VersionCheckApiView.as_view(), name='version_check_api'),
    path('api/auth/check/', AuthCheckApiView.as_view(), name='auth_check_api'),
    path('api/my-assignments/', MyAssignmentsApiView.as_view(), name='my_assignments_api'),
    path('api/assignment/upload/', AssignmentUploadAPIView.as_view(), name='assignment_upload_api'),
]
