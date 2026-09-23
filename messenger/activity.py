from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

# Реже — лишний write на каждый запрос, чаще — last_seen перестаёт быть «активностью»
LAST_SEEN_THROTTLE = timedelta(seconds=60)


def touch_last_seen(user) -> None:
    """
    Обновляет last_seen пользователя, но не чаще LAST_SEEN_THROTTLE.
    Условие троттлинга продублировано в самом UPDATE — на случай, если
    `user` в памяти уже протух (например, в долгоживущем WS-соединении).
    """
    now = timezone.now()
    if user.last_seen and now - user.last_seen < LAST_SEEN_THROTTLE:
        return

    User = get_user_model()
    updated = (
        User.objects.filter(pk=user.pk)
        .filter(Q(last_seen__isnull=True) | Q(last_seen__lt=now - LAST_SEEN_THROTTLE))
        .update(last_seen=now)
    )
    if updated:
        user.last_seen = now
