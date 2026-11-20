from django.urls import path

from .views import (
    UserListView, UserCreateView, UserUpdateView, ChangePasswordView, HomePageView, SelectCityView, BranchListView,
    BranchCreateView, BranchUpdateView, CityListView, CityCreateView, CityUpdateView, UserAssociateView,
    UserDeleteView
)

app_name = 'accounts'

urlpatterns = [
    path('', UserListView.as_view(), name='list'),
    path('create/', UserCreateView.as_view(), name='create'),
    path('delete/<int:pk>/', UserDeleteView.as_view(), name='delete'),
    path('associate/', UserAssociateView.as_view(), name='associate'),
    path('<int:pk>/edit/', UserUpdateView.as_view(), name='edit'),
    path('<int:pk>/change_password/', ChangePasswordView.as_view(), name='change_password'),
    path('go_home/', HomePageView.as_view(), name='go_home'),
    path('set-city/', SelectCityView.as_view(), name='set_current_city'),

    path('branch/', BranchListView.as_view(), name='branch_list'),
    path('branch/create/', BranchCreateView.as_view(), name='branch_create'),
    path('branch/<int:pk>/', BranchUpdateView.as_view(), name='branch_update'),

    path('city/', CityListView.as_view(), name='city_list'),
    path('city/create/', CityCreateView.as_view(), name='city_create'),
    path('city/<int:pk>/', CityUpdateView.as_view(), name='city_update'),
]
