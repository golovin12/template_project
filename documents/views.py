from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .auth import documents_login_required
from .controllers import create_folder, delete_file, upload_file
from .forms import (
    DocumentsLoginForm,
    DocumentsRegistrationForm,
    DocumentFolderForm,
    DocumentSelectionForm,
    DocumentUploadForm,
)
from .middleware import DocumentsUserMiddleware
from .models import DocumentFile, DocumentFolder
from .storage import get_user_document, open_document
from .zip import create_zip_response


def _render_index(
    request,
    current_folder=None,
    folder_form=None,
    upload_form=None,
    selection_form=None,
):
    user = request.documents_user

    folders = DocumentFolder.objects.filter(user=user)
    files = DocumentFile.objects.filter(
        user=user,
        folder=current_folder,
    )

    if folder_form is None:
        folder_form = DocumentFolderForm(user=user)

    if upload_form is None:
        upload_form = DocumentUploadForm(
            user=user,
            initial={'folder': current_folder},
        )

    if selection_form is None:
        selection_form = DocumentSelectionForm(user=user)

    return render(request, 'documents/index.html', {
        'folders': folders,
        'current_folder': current_folder,
        'files': files,
        'folder_form': folder_form,
        'upload_form': upload_form,
        'selection_form': selection_form,
    })


def register(request):
    if request.documents_user is not None:
        return redirect('documents:index')

    form = DocumentsRegistrationForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error(
                'username',
                'Пользователь с таким логином уже существует.',
            )
        else:
            request.session.cycle_key()
            request.session[DocumentsUserMiddleware.session_key] = user.pk
            return redirect('documents:index')

    return render(request, 'documents/register.html', {'form': form})


def login(request):
    if request.documents_user is not None:
        return redirect('documents:index')

    form = DocumentsLoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        request.session.cycle_key()
        request.session[DocumentsUserMiddleware.session_key] = (
            form.cleaned_data['user'].pk
        )
        return redirect('documents:index')

    return render(request, 'documents/login.html', {'form': form})


@require_POST
@documents_login_required
def logout(request):
    request.session.pop(DocumentsUserMiddleware.session_key, None)
    request.session.cycle_key()

    messages.success(request, 'Вы вышли из своего аккаунта.')

    return redirect('documents:login')


@documents_login_required
def index(request):
    user = request.documents_user
    folder_id = request.GET.get('folder')
    current_folder = None

    if folder_id:
        current_folder = DocumentFolder.objects.filter(
            pk=folder_id,
            user=user,
        ).first()

        if current_folder is None:
            return redirect('documents:index')

    return _render_index(request, current_folder=current_folder)


@require_POST
@documents_login_required
def folder_create(request):
    form = DocumentFolderForm(
        request.POST,
        user=request.documents_user,
    )

    if form.is_valid():
        try:
            create_folder(
                request.documents_user,
                form.cleaned_data['name'],
            )
        except ValidationError as error:
            form.add_error('name', error)
        else:
            messages.success(request, 'Папка создана.')
            return redirect('documents:index')

    return _render_index(
        request,
        folder_form=form,
    )


@require_POST
@documents_login_required
def file_upload(request):
    form = DocumentUploadForm(
        request.POST,
        request.FILES,
        user=request.documents_user,
    )

    if form.is_valid():
        folder = form.cleaned_data['folder']

        try:
            upload_file(
                user=request.documents_user,
                uploaded_file=form.cleaned_data['file'],
                folder_id=folder.pk if folder else None,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Файл загружен.')

            if folder:
                return redirect(f'{reverse("documents:index")}?folder={folder.pk}')

            return redirect('documents:index')

    return _render_index(
        request,
        upload_form=form,
    )


@require_POST
@documents_login_required
def file_delete(request, file_id):
    try:
        delete_file(request.documents_user, file_id)
    except ValidationError:
        messages.error(request, 'Файл не найден.')
    else:
        messages.success(request, 'Файл удалён.')

    return redirect('documents:index')


@documents_login_required
def file_download(request, file_id):
    try:
        document = get_user_document(request.documents_user, file_id)
    except ValidationError:
        messages.error(request, 'Файл не найден.')
        return redirect('documents:index')

    return FileResponse(
        open_document(document),
        as_attachment=True,
        filename=document.original_name,
    )


@require_POST
@documents_login_required
def files_download(request):
    form = DocumentSelectionForm(
        request.POST,
        user=request.documents_user,
    )

    if not form.is_valid():
        messages.error(request, 'Выбери файлы для скачивания.')
        return redirect('documents:index')

    file_ids = list(
        form.cleaned_data['files'].values_list('pk', flat=True)
    )

    try:
        return create_zip_response(request.documents_user, file_ids)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect('documents:index')
