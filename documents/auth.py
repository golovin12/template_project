from functools import wraps


def documents_login_required(view_func):
    @wraps(view_func)
    async def wrapper(request, *args, **kwargs):
        if request.documents_user is None:
            from django.shortcuts import redirect
            return redirect('documents:login')

        return await view_func(request, *args, **kwargs)

    return wrapper
