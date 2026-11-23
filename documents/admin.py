from django.contrib import admin

from .models import DocumentsUser, DocumentFolder, DocumentFile


@admin.register(DocumentsUser)
class DocumentsUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('username',)
    readonly_fields = ('created_at',)


@admin.register(DocumentFolder)
class DocumentFolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(DocumentFile)
class DocumentFileAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'user', 'folder', 'size', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('original_name', 'user__username')
    readonly_fields = ('created_at', 'size')
