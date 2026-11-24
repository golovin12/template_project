from typing import AsyncIterator

from asgiref.sync import sync_to_async

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models.functions import Lower
from django.http import StreamingHttpResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from common_tools.async_files import storage_client, storage_file_iterator
from common_tools.images import acompress_image
from .auth import documents_login_required
from .controllers import delete_file, save_folder
from .forms import (
    DocumentsLoginForm, DocumentsRegistrationForm, DocumentFolderForm, DocumentSelectionForm, DocumentUploadForm
)
from .middleware import DocumentsHttpRequest, DocumentsUserMiddleware
from .models import DocumentFile, DocumentFolder
from .zip import create_zip_response


def _index_url(folder: DocumentFolder | None = None) -> str:
    url = reverse('documents:index')
    return f'{url}?folder={folder.pk}' if folder else url


async def _get_folder(user, folder_id: str | None) -> DocumentFolder | None:
    if not folder_id:
        return None

    return await DocumentFolder.objects.filter(pk=folder_id, user=user).afirst()


async def _render_index(
        request: DocumentsHttpRequest,
        current_folder: DocumentFolder | None = None,
        folder_form: DocumentFolderForm | None = None,
        upload_form: DocumentUploadForm | None = None,
) -> HttpResponse:
    user = request.documents_user

    folders = []

    if current_folder is None:
        folders = [
            folder async for folder in DocumentFolder.objects.filter(user=user).order_by(Lower('name'), 'pk')
        ]

    files = [
        document async for document in DocumentFile.objects.filter(
            user=user, folder=current_folder
        ).order_by(Lower('original_name'), 'pk')
    ]

    return render(request, 'documents/index.html', {
        'folders': folders,
        'current_folder': current_folder,
        'files': files,
        'folder_form': folder_form or DocumentFolderForm(user=user),
        'upload_form': upload_form or DocumentUploadForm(user=user, initial={'folder': current_folder}),
    })


def _validate_form(form_class, *args, **kwargs):
    form = form_class(*args, **kwargs)
    return form, form.is_valid()


async def _get_selected_file_ids(form: DocumentSelectionForm) -> list[int]:
    return [document.pk async for document in form.cleaned_data['files']]


async def _file_iterator(filename: str) -> AsyncIterator[bytes]:
    async with storage_client() as s3:
        async for chunk in storage_file_iterator(filename, s3):
            yield chunk


async def register(request: DocumentsHttpRequest):
    if request.documents_user is not None:
        return redirect('documents:index')

    form, is_valid = await sync_to_async(_validate_form)(DocumentsRegistrationForm, request.POST or None)

    if request.method == 'POST' and is_valid:
        user = form.save(commit=False)

        try:
            await user.asave()
        except IntegrityError:
            form.add_error('username', 'Пользователь с таким логином уже существует.')
        else:
            await request.session.acycle_key()
            await request.session.aset(DocumentsUserMiddleware.session_key, user.pk)
            return redirect('documents:index')

    return render(request, 'documents/register.html', {'form': form})


async def login(request: DocumentsHttpRequest):
    if request.documents_user is not None:
        return redirect('documents:index')

    form, is_valid = await sync_to_async(_validate_form)(DocumentsLoginForm, request.POST or None)

    if request.method == 'POST' and is_valid:
        await request.session.acycle_key()
        await request.session.aset(DocumentsUserMiddleware.session_key, form.cleaned_data['user'].pk)
        return redirect('documents:index')

    return render(request, 'documents/login.html', {'form': form})


@require_POST
@documents_login_required
async def logout(request: DocumentsHttpRequest):
    await request.session.apop(DocumentsUserMiddleware.session_key, None)
    await request.session.acycle_key()

    messages.success(request, 'Вы вышли из своего аккаунта.')

    return redirect('documents:login')


@documents_login_required
async def index(request: DocumentsHttpRequest):
    folder_id = request.GET.get('folder')
    current_folder = await _get_folder(request.documents_user, folder_id)

    if folder_id and current_folder is None:
        return redirect('documents:index')

    return await _render_index(request, current_folder=current_folder)


@require_POST
@documents_login_required
async def folder_create(request: DocumentsHttpRequest):
    form, is_valid = await sync_to_async(_validate_form)(
        DocumentFolderForm, request.POST, user=request.documents_user
    )

    if is_valid:
        folder = form.save(commit=False)

        try:
            await save_folder(folder)
        except IntegrityError:
            form.add_error('name', 'Папка с таким названием уже существует.')
        else:
            messages.success(request, 'Папка создана.')
            return redirect('documents:index')

    return await _render_index(request, folder_form=form)


@require_POST
@documents_login_required
async def file_upload(request: DocumentsHttpRequest):
    form, is_valid = await sync_to_async(_validate_form)(
        DocumentUploadForm, request.POST, request.FILES, user=request.documents_user
    )

    if is_valid:
        document = form.save(commit=False)

        uploaded_file = form.cleaned_data['file']
        original_name = uploaded_file.name.replace('\\', '/').split('/')[-1][:255]

        if not original_name:
            form.add_error('file', 'Некорректное имя файла.')
        else:
            processed_file = await acompress_image(uploaded_file)

            document.original_name = original_name
            document.size = processed_file.size
            document.file = processed_file

            folder = document.folder

            await document.asave()

            messages.success(request, 'Файл загружен.')

            return redirect(_index_url(folder))

    current_folder = form.cleaned_data.get('folder')

    return await _render_index(request, current_folder=current_folder, upload_form=form)


@require_POST
@documents_login_required
async def file_delete(request: DocumentsHttpRequest, file_id: int):
    current_folder = await _get_folder(request.documents_user, request.GET.get('folder'))

    try:
        await delete_file(request.documents_user, file_id)
    except ValidationError:
        messages.error(request, 'Файл не найден.')
    else:
        messages.success(request, 'Файл удалён.')

    return redirect(_index_url(current_folder))


@documents_login_required
async def file_download(request: DocumentsHttpRequest, file_id: int):
    try:
        document = await DocumentFile.objects.aget(pk=file_id, user=request.documents_user)
    except DocumentFile.DoesNotExist:
        messages.error(request, 'Файл не найден.')
        current_folder = await _get_folder(request.documents_user, request.GET.get('folder'))
        return redirect(_index_url(current_folder))

    response = StreamingHttpResponse(_file_iterator(document.file.name), content_type='application/octet-stream')
    response['Content-Disposition'] = content_disposition_header(True, document.original_name)

    return response


@require_POST
@documents_login_required
async def files_download(request: DocumentsHttpRequest):
    current_folder = await _get_folder(request.documents_user, request.GET.get('folder'))

    form, is_valid = await sync_to_async(_validate_form)(
        DocumentSelectionForm, request.POST, user=request.documents_user
    )

    if not is_valid:
        messages.error(request, 'Выбери файлы для скачивания.')
        return redirect(_index_url(current_folder))

    file_ids = await _get_selected_file_ids(form)

    try:
        return await create_zip_response(request.documents_user, file_ids)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect(_index_url(current_folder))
