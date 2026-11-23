from functools import wraps

from django.shortcuts import redirect


def documents_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.documents_user is None:
            return redirect('documents:login')

        return view_func(request, *args, **kwargs)

    return wrapper
