from captcha.fields import CaptchaField
from django.contrib.auth.forms import AuthenticationForm

from common_tools.widgets import CustomCaptchaTextInput


class LoginForm(AuthenticationForm):
    captcha = CaptchaField(widget=CustomCaptchaTextInput(attrs={'placeholder': 'Введите результат решения примера'}),
                           label='')
