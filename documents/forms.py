from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import DocumentsUser, DocumentFile, DocumentFolder


class DocumentsRegistrationForm(forms.ModelForm):
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='Повторите пароль', widget=forms.PasswordInput)

    class Meta:
        model = DocumentsUser
        fields = ('username',)
        labels = {'username': 'Логин'}

    def clean_username(self):
        username = self.cleaned_data['username'].strip()

        if DocumentsUser.objects.filter(username__iexact=username).exists():
            raise ValidationError('Пользователь с таким логином уже существует.')

        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'Пароли не совпадают.')

        if password:
            try:
                validate_password(password)
            except ValidationError as error:
                self.add_error('password', error)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()

        return user


class DocumentsLoginForm(forms.Form):
    username = forms.CharField(max_length=150, label='Логин')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username', '').strip()
        password = cleaned_data.get('password')

        if not username or not password:
            return cleaned_data

        user = DocumentsUser.objects.filter(username__iexact=username, is_active=True).first()

        if user is None or not user.check_password(password):
            raise ValidationError('Неверный логин или пароль.')

        cleaned_data['username'] = username
        cleaned_data['user'] = user

        return cleaned_data


class DocumentFolderForm(forms.ModelForm):
    class Meta:
        model = DocumentFolder
        fields = ('name',)
        labels = {'name': 'Название папки'}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.instance.user = user

    def clean_name(self):
        name = self.cleaned_data['name'].strip()

        if DocumentFolder.objects.filter(user=self.user, name__iexact=name).exists():
            raise ValidationError('Папка с таким названием уже существует.')

        return name


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = DocumentFile
        fields = ('file', 'folder')
        labels = {
            'file': 'Файл',
            'folder': 'Папка',
        }
        widgets = {
            'folder': forms.HiddenInput(),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.user = user
        self.fields['folder'].queryset = DocumentFolder.objects.filter(user=user)
        self.fields['folder'].required = False
