from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token: str):
    """Декодирует JWT и возвращает пользователя. Async-safe."""
    try:
        validated_token = AccessToken(token)
        user_id = validated_token["user_id"]
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, KeyError, User.DoesNotExist):
        return AnonymousUser()


async def get_user_from_scope(scope: dict):
    """
    Извлекает JWT из query string scope и возвращает пользователя.
    Используется в Consumer.connect().
    """
    query_string = scope.get("query_string", b"").decode("utf-8")
    params = parse_qs(query_string)
    token_list = params.get("token", [])

    if not token_list:
        return AnonymousUser()

    return await get_user_from_token(token_list[0])
