from django import template

register = template.Library()


@register.filter
def default_dict(value) -> dict:
    if value is None:
        return {}
    return value


@register.filter
def get_item(dictionary, key) -> any:
    return dictionary.get(key)
