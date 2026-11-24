from datetime import date, datetime, timedelta

MONTH_NAMES_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
    7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}

MONTH_ADDITIONAL_NAMES_RU = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
    7: 'июля', 8: 'августа', 9: 'Сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
}


def parse_dates_from_string(input_string: str) -> tuple[str | None, str | None]:
    """
    Парсит строку, содержащую одну или две даты, разделенные " - ".

    Args:
        input_string: Строка для парсинга (может содержать одну дату или две через " - ")

    Returns:
        Кортеж из (date1, date2), где date2 будет None, если в строке только одна дата
    """

    def try_parse_date(date_str: str) -> date | None:
        try:
            return datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            return None

    parts = input_string.strip().split(" - ", maxsplit=1)
    date1 = try_parse_date(parts[0])
    date2 = None
    if len(parts) == 2 and date1 is not None:
        date2 = try_parse_date(parts[1])

    return date1, date2


def get_last_day_prev_month() -> date:
    """Последний день прошедшего месяца"""
    today = datetime.now().date()
    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    return last_day_previous_month


def get_first_day_prev_month() -> date:
    """Первый день прошедшего месяца"""
    return get_last_day_prev_month().replace(day=1)
