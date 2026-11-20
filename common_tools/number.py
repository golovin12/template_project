from django.utils.formats import number_format


def format_money(value, decimal_pos: int = 2) -> str:
    return number_format(value, decimal_pos=decimal_pos, force_grouping=True)
