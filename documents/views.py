from asgiref.sync import sync_to_async

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from .auth import documents_login_required
from .controllers import create_folder, delete_file, upload_file
from .forms import (
    DocumentsLoginForm, DocumentsRegistrationForm, DocumentFolderForm, DocumentSelectionForm, DocumentUploadForm
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


def _validate_form(form_class, *args, **kwargs):
    form = form_class(*args, **kwargs)
    return form, form.is_valid()


def _save_registration(form):
    with transaction.atomic():
        return form.save()


def _get_selected_file_ids(form):
    return list(form.cleaned_data['files'].values_list('pk', flat=True))


@sync_to_async
def _open_document_async(document):
    return open_document(document)


async def _file_iterator(file_object):
    try:
        while True:
            chunk = await sync_to_async(file_object.read)(
                64 * 1024,
            )

            if not chunk:
                break

            yield chunk
    finally:
        await sync_to_async(file_object.close)()


async def register(request):
    if request.documents_user is not None:
        return redirect('documents:index')

    form, is_valid = await sync_to_async(_validate_form)(
        DocumentsRegistrationForm,
        request.POST or None,
    )

    if request.method == 'POST' and is_valid:
        try:
            user = await sync_to_async(_save_registration)(form)
        except IntegrityError:
            form.add_error(
                'username',
                'Пользователь с таким логином уже существует.',
            )
        else:
            await request.session.acycle_key()
            await request.session.aset(
                DocumentsUserMiddleware.session_key,
                user.pk,
            )
            return redirect('documents:index')

    return await sync_to_async(render)(
        request,
        'documents/register.html',
        {'form': form},
        content_type=None,
        using=None,
        status=None,
    )


async def login(request):
    if request.documents_user is not None:
        return redirect('documents:index')

    form, is_valid = await sync_to_async(_validate_form)(
        DocumentsLoginForm,
        request.POST or None,
    )

    if request.method == 'POST' and is_valid:
        await request.session.acycle_key()
        await request.session.aset(
            DocumentsUserMiddleware.session_key,
            form.cleaned_data['user'].pk,
        )
        return redirect('documents:index')

    return await sync_to_async(render)(
        request,
        'documents/login.html',
        {'form': form},
        content_type=None,
        using=None,
        status=None,
    )


@require_POST
@documents_login_required
async def logout(request):
    await request.session.apop(
        DocumentsUserMiddleware.session_key,
        None,
    )
    await request.session.acycle_key()

    messages.success(request, 'Вы вышли из своего аккаунта.')

    return redirect('documents:login')


@documents_login_required
async def index(request):
    user = request.documents_user
    folder_id = request.GET.get('folder')
    current_folder = None

    if folder_id:
        current_folder = await DocumentFolder.objects.filter(
            pk=folder_id,
            user=user,
        ).afirst()

        if current_folder is None:
            return redirect('documents:index')

    return await sync_to_async(_render_index)(
        request,
        current_folder=current_folder,
        upload_form=None,
        folder_form=None,
        selection_form=None,
    )


@require_POST
@documents_login_required
async def folder_create(request):
    form, is_valid = await sync_to_async(_validate_form)(
        DocumentFolderForm,
        request.POST,
        user=request.documents_user,
    )

    if is_valid:
        try:
            await create_folder(
                request.documents_user,
                form.cleaned_data['name'],
            )
        except ValidationError as error:
            form.add_error('name', error)
        else:
            messages.success(request, 'Папка создана.')
            return redirect('documents:index')

    return await sync_to_async(_render_index)(
        request,
        folder_form=form,
        upload_form=None,
        current_folder=None,
        selection_form=None,
    )


@require_POST
@documents_login_required
async def file_upload(request):
    form, is_valid = await sync_to_async(_validate_form)(
        DocumentUploadForm,
        request.POST,
        request.FILES,
        user=request.documents_user,
    )

    if is_valid:
        folder = form.cleaned_data['folder']

        try:
            await upload_file(
                user=request.documents_user,
                uploaded_file=form.cleaned_data['file'],
                folder_id=folder.pk if folder else None,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Файл загружен.')

            if folder:
                return redirect(
                    f'{reverse("documents:index")}?folder={folder.pk}'
                )

            return redirect('documents:index')

    return await sync_to_async(_render_index)(
        request,
        upload_form=form,
        folder_form=None,
        current_folder=None,
        selection_form=None,
    )


@require_POST
@documents_login_required
async def file_delete(request, file_id):
    try:
        await delete_file(request.documents_user, file_id)
    except ValidationError:
        messages.error(request, 'Файл не найден.')
    else:
        messages.success(request, 'Файл удалён.')

    return redirect('documents:index')


@documents_login_required
async def file_download(request, file_id):
    try:
        document = await get_user_document(
            request.documents_user,
            file_id,
        )
    except ValidationError:
        messages.error(request, 'Файл не найден.')
        return redirect('documents:index')

    file_object = await _open_document_async(document)

    response = StreamingHttpResponse(
        _file_iterator(file_object),
        content_type='application/octet-stream',
    )
    response['Content-Disposition'] = content_disposition_header(
        True,
        document.original_name,
    )

    return response


@require_POST
@documents_login_required
async def files_download(request):
    form, is_valid = await sync_to_async(_validate_form)(
        DocumentSelectionForm,
        request.POST,
        user=request.documents_user,
    )

    if not is_valid:
        messages.error(request, 'Выбери файлы для скачивания.')
        return redirect('documents:index')

    file_ids = await sync_to_async(_get_selected_file_ids)(form)

    try:
        return await create_zip_response(
            request.documents_user,
            file_ids,
        )
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect('documents:index')
