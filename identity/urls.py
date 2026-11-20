from django.urls import path

from .views import LoginView, LogoutView, AuthorizeAsView, SelectOrganizationView

app_name = 'identity'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('authorize/', AuthorizeAsView.as_view(), name='authorize'),
    path('select-organization/', SelectOrganizationView.as_view(), name='select_organization'),
]
