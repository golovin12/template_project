import markdown

from django.template.loader import render_to_string
from django.utils.safestring import mark_safe


def load_and_render_md(file_path: str) -> str:
    """Загружает .md файл и конвертирует в HTML"""
    try:
        content = render_to_string('promoter_app/docs/privacy_policy.md')

        html = markdown.markdown(content, extensions=['extra', 'nl2br'])
        return mark_safe(html)

    except Exception as e:
        return f'<p class="text-danger">Ошибка: {e}</p>'
