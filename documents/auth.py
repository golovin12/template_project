from functools import wraps

from django.shortcuts import redirect

from documents.middleware import DocumentsHttpRequest


def documents_login_required(view_func):
    @wraps(view_func)
    async def wrapper(request: DocumentsHttpRequest, *args, **kwargs):
        if request.documents_user is None:
            return redirect('documents:login')

        return await view_func(request, *args, **kwargs)

    return wrapper
