def truncate_text(text: str, max_length: int) -> str:
    """
    Обрезает текст до указанной длины, добавляя многоточие, если текст был обрезан.

    :param text: Исходный текст
    :param max_length: Максимальная длина текста (включая многоточие, если оно будет добавлено)
    :return: Обрезанный текст с многоточием, если необходимо
    """
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return "..."[:max_length]
    return text[:max_length - 3] + "..."
