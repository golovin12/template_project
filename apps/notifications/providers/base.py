import re
from abc import ABC, abstractmethod


def clean_html(text: str) -> str:
    """Очищает HTML от плохих тегов"""
    text = re.sub(r'<([a-z]+)>\s*</\1>', '', text)

    tags = ['b', 'i', 'u', 's', 'code', 'pre']
    for tag in tags:
        open_count = text.count(f'<{tag}>')
        close_count = text.count(f'</{tag}>')

        if open_count > close_count:
            text += f'</{tag}>' * (open_count - close_count)

    for tag in tags:
        text = re.sub(f'<{tag}><{tag}>', f'<{tag}>', text)
        text = re.sub(f'</{tag}></{tag}>', f'</{tag}>', text)

    return text


class BaseNotificationProvider(ABC):

    @abstractmethod
    def send(self, message: str, is_html: bool = False) -> bool:
        pass
