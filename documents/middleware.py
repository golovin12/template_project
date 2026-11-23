from .models import DocumentsUser


class DocumentsUserMiddleware:
    session_key = 'documents_user_id'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = request.session.get(self.session_key)

        request.documents_user = (
            DocumentsUser.objects.filter(
                pk=user_id,
                is_active=True,
            ).first() if user_id else None
        )

        return self.get_response(request)
