from django.urls import path

from . import views


app_name = 'documents'

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('folders/create/', views.folder_create, name='folder_create'),
    path('files/upload/', views.file_upload, name='file_upload'),
    path('files/<int:file_id>/download/', views.file_download, name='file_download'),
    path('files/<int:file_id>/delete/', views.file_delete, name='file_delete'),
    path('files/download/', views.files_download, name='files_download'),
]
