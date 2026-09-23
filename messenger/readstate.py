from django.db.models import Count, F, Q

from messenger.models import Membership


def unread_counts(user, chat_ids) -> dict:
    """
    Сколько сообщений в каждом чате пользователь ещё не читал.

    Непрочитанное — сообщение, созданное позже Membership.last_read_at и не от
    самого пользователя. Один запрос на весь список чатов, условие
    created_at > курсора ложится на индекс (chat, created_at). Ключи — str(id),
    чтобы один конвенция была у REST- и WS-вызовов.
    """
    chat_ids = list(chat_ids)
    if not chat_ids:
        return {}

    rows = (
        Membership.objects.filter(user=user, chat_id__in=chat_ids)
        .annotate(
            unread=Count(
                "chat__messages",
                filter=Q(chat__messages__created_at__gt=F("last_read_at"))
                & ~Q(chat__messages__sender=user),
            )
        )
        .values_list("chat_id", "unread")
    )
    return {str(chat_id): unread for chat_id, unread in rows}


def unread_counts_per_user(chat_id, exclude_user_id=None) -> dict:
    """
    Непрочитанное по каждому участнику чата — одним запросом.

    Нужен для уведомлений: у каждого получателя свой курсор, поэтому посчитать
    один раз и разослать нельзя. Отправителя исключаем — свои сообщения не
    уведомление, а его другие вкладки и так получают message в WS-группе чата.
    Условие `sender != <этот участник>` выражается F("user"): Django подставляет
    колонку membership.user_id, а GROUP BY по PK позволяет на неё ссылаться.
    """
    memberships = Membership.objects.filter(chat_id=chat_id)
    if exclude_user_id is not None:
        memberships = memberships.exclude(user_id=exclude_user_id)

    rows = memberships.annotate(
        unread=Count(
            "chat__messages",
            filter=Q(chat__messages__created_at__gt=F("last_read_at"))
            & ~Q(chat__messages__sender=F("user")),
        )
    ).values_list("user_id", "unread")
    return {str(uid): unread for uid, unread in rows}
