from django.contrib import admin

from .models import DocumentsUser, DocumentFolder, DocumentFile


@admin.register(DocumentsUser)
class DocumentsUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('username',)
    readonly_fields = ('password', 'created_at')
    ordering = ('username',)

    def has_add_permission(self, request):
        return False


@admin.register(DocumentFolder)
class DocumentFolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'user__username')
    readonly_fields = ('created_at',)
    list_select_related = ('user',)
    autocomplete_fields = ('user',)
    ordering = ('name',)


@admin.register(DocumentFile)
class DocumentFileAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'user', 'folder', 'size', 'created_at')
    list_filter = ('created_at', 'folder')
    search_fields = ('original_name', 'user__username', 'folder__name')
    readonly_fields = ('created_at', 'size')
    list_select_related = ('user', 'folder')
    autocomplete_fields = ('user', 'folder')
    ordering = ('-created_at',)
