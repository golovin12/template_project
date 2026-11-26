from asgiref.sync import markcoroutinefunction

from django.http import HttpRequest, HttpResponse

from .models import DocumentsUser


class DocumentsHttpRequest(HttpRequest):
    documents_user: DocumentsUser | None


class DocumentsUserMiddleware:
    session_key = 'documents_user_id'
    sync_capable = False
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        markcoroutinefunction(self)

    async def __call__(self, request: DocumentsHttpRequest) -> HttpResponse:
        if not request.path_info.startswith('/documents/'):
            return await self.get_response(request)

        user_id = await request.session.aget(self.session_key)

        request.documents_user = (
            await DocumentsUser.objects.filter(pk=user_id, is_active=True).afirst() if user_id else None
        )

        return await self.get_response(request)
