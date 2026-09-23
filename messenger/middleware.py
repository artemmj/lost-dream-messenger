from .activity import touch_last_seen


class LastSeenMiddleware:
    """
    Отмечает активность пользователя на любом авторизованном запросе (троттлинг
    внутри touch_last_seen).

    Проверяем request.user ПОСЛЕ вызова view: DRF аутентифицирует запрос уже
    внутри view и пробрасывает пользователя в исходный Django HttpRequest,
    поэтому до view там всегда аноним (в т.ч. для JWT).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            touch_last_seen(user)

        return response
