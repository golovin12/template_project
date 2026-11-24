from typing import AsyncIterator

from asgiref.sync import sync_to_async

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import StreamingHttpResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from common_tools.images import acompress_image
from .auth import documents_login_required
from .controllers import delete_file
from .forms import (
    DocumentsLoginForm, DocumentsRegistrationForm, DocumentFolderForm, DocumentSelectionForm, DocumentUploadForm
)
from .middleware import DocumentsHttpRequest, DocumentsUserMiddleware
from .models import DocumentFile, DocumentFolder
from .storage import get_user_document, open_document
from .zip import create_zip_response


def _render_index(
        request: DocumentsHttpRequest, current_folder: DocumentFolder | None = None,
        folder_form: DocumentFolderForm | None = None, upload_form: DocumentUploadForm | None = None,
        selection_form: DocumentSelectionForm | None = None,
) -> HttpResponse:
    user = request.documents_user

    if folder_form is None:
        folder_form = DocumentFolderForm(user=user)

    if upload_form is None:
        upload_form = DocumentUploadForm(user=user, initial={'folder': current_folder})

    if selection_form is None:
        selection_form = DocumentSelectionForm(user=user)

    return render(request, 'documents/index.html', {
        'folders': DocumentFolder.objects.filter(user=user),
        'current_folder': current_folder,
        'files': DocumentFile.objects.filter(user=user, folder=current_folder),
        'folder_form': folder_form,
        'upload_form': upload_form,
        'selection_form': selection_form,
    })


def _validate_form(form_class, *args, **kwargs):
    form = form_class(*args, **kwargs)
    return form, form.is_valid()


def _get_selected_file_ids(form: DocumentSelectionForm) -> list[int]:
    return list(form.cleaned_data['files'].values_list('pk', flat=True))


async def _file_iterator(file_object) -> AsyncIterator[bytes]:
    try:
        while True:
            chunk = await sync_to_async(file_object.read)(64 * 1024)

            if not chunk:
                break

            yield chunk
    finally:
        await sync_to_async(file_object.close)()


async def register(request: DocumentsHttpRequest):
    if request.documents_user is not None:
        return redirect('documents:index')

    form, is_valid = await sync_to_async(_validate_form)(DocumentsRegistrationForm, request.POST or None)

    if request.method == 'POST' and is_valid:
        user = await sync_to_async(form.save)(commit=False)

        try:
            await user.asave()
        except IntegrityError:
            form.add_error('username', 'Пользователь с таким логином уже существует.')
        else:
            await request.session.acycle_key()
            await request.session.aset(DocumentsUserMiddleware.session_key, user.pk)
            return redirect('documents:index')

    return await sync_to_async(render)(request, 'documents/register.html', {'form': form})


async def login(request: DocumentsHttpRequest):
    if request.documents_user is not None:
        return redirect('documents:index')

    form, is_valid = await sync_to_async(_validate_form)(DocumentsLoginForm, request.POST or None)

    if request.method == 'POST' and is_valid:
        await request.session.acycle_key()
        await request.session.aset(DocumentsUserMiddleware.session_key, form.cleaned_data['user'].pk)
        return redirect('documents:index')

    return await sync_to_async(render)(request, 'documents/login.html', {'form': form})


@require_POST
@documents_login_required
async def logout(request: DocumentsHttpRequest):
    await request.session.apop(DocumentsUserMiddleware.session_key, None)
    await request.session.acycle_key()

    messages.success(request, 'Вы вышли из своего аккаунта.')

    return redirect('documents:login')


@documents_login_required
async def index(request: DocumentsHttpRequest):
    user = request.documents_user
    folder_id = request.GET.get('folder')
    current_folder = None

    if folder_id:
        current_folder = await DocumentFolder.objects.filter(pk=folder_id, user=user).afirst()

        if current_folder is None:
            return redirect('documents:index')

    return await sync_to_async(_render_index)(request, current_folder=current_folder)


@require_POST
@documents_login_required
async def folder_create(request: DocumentsHttpRequest):
    form, is_valid = await sync_to_async(_validate_form)(
        DocumentFolderForm, request.POST, user=request.documents_user
    )

    if is_valid:
        folder = await sync_to_async(form.save)(commit=False)

        try:
            await folder.asave()
        except IntegrityError:
            form.add_error('name', 'Папка с таким названием уже существует.')
        else:
            messages.success(request, 'Папка создана.')
            return redirect('documents:index')

    return await sync_to_async(_render_index)(request, folder_form=form)


@require_POST
@documents_login_required
async def file_upload(request: DocumentsHttpRequest):
    form, is_valid = await sync_to_async(_validate_form)(
        DocumentUploadForm, request.POST, request.FILES, user=request.documents_user
    )

    if is_valid:
        document = await sync_to_async(form.save)(commit=False)

        uploaded_file = form.cleaned_data['file']
        original_name = uploaded_file.name.replace('\\', '/').split('/')[-1]
        original_name = original_name[:255]

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

            if folder:
                return redirect(f'{reverse("documents:index")}?folder={folder.pk}')

            return redirect('documents:index')

    current_folder = form.cleaned_data.get('folder')

    return await sync_to_async(_render_index)(request, current_folder=current_folder, upload_form=form)


@require_POST
@documents_login_required
async def file_delete(request: DocumentsHttpRequest, file_id: int):
    try:
        await delete_file(request.documents_user, file_id)
    except ValidationError:
        messages.error(request, 'Файл не найден.')
    else:
        messages.success(request, 'Файл удалён.')

    return redirect('documents:index')


@documents_login_required
async def file_download(request: DocumentsHttpRequest, file_id: int):
    try:
        document = await get_user_document(request.documents_user, file_id)
    except ValidationError:
        messages.error(request, 'Файл не найден.')
        return redirect('documents:index')

    file_object = await sync_to_async(open_document)(document)

    response = StreamingHttpResponse(_file_iterator(file_object), content_type='application/octet-stream')
    response['Content-Disposition'] = content_disposition_header(True, document.original_name)

    return response


@require_POST
@documents_login_required
async def files_download(request: DocumentsHttpRequest):
    form, is_valid = await sync_to_async(_validate_form)(
        DocumentSelectionForm, request.POST, user=request.documents_user
    )

    if not is_valid:
        messages.error(request, 'Выбери файлы для скачивания.')
        return redirect('documents:index')

    file_ids = await sync_to_async(_get_selected_file_ids)(form)

    try:
        return await create_zip_response(request.documents_user, file_ids)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect('documents:index')
