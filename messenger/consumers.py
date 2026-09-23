import os

import redis.asyncio as aioredis
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from .models import Membership, Message
from .ws_auth import get_user_from_scope

PRESENCE_KEY = "messenger:presence"

_redis_client = None


def get_redis() -> aioredis.Redis:
    """Ленивый singleton Redis-клиента для presence-реестра."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            f"redis://{os.environ.get('REDIS_HOST', 'redis')}:6379/0",
            decode_responses=True,
        )
    return _redis_client


def message_payload(msg: Message) -> dict:
    """Единый формат сообщения для WS-рассылки (используется consumer'ом и REST)."""
    return {
        "id": str(msg.id),
        "chat": str(msg.chat_id),
        "sender": {
            "id": str(msg.sender.id),
            "phone": msg.sender.phone,
            "first_name": msg.sender.first_name,
            "last_name": msg.sender.last_name,
        },
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
        "is_read": msg.is_read,
    }


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer для чата.
    Подключение: ws://host/ws/chat/<uuid>/?token=<jwt>
    """

    async def connect(self):
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.group_name = f"chat_{self.chat_id}"
        self.user = await get_user_from_scope(self.scope)

        # Отказ анонимам
        if isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        # Проверка участия в чате
        is_member = await self._check_membership()
        if not is_member:
            await self.close(code=4003)
            return

        # Присоединяемся к группе
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # помечаем сообщения как прочитанные
        had_unread = await self._mark_messages_read()
        if had_unread:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "messages.read",
                    "reader_id": str(self.user.id),
                },
            )

        # Обновляем last_seen
        await self._update_last_seen()

        # Presence: инкрементируем счётчик соединений пользователя.
        # Online анонсируется только при первом соединении (учитываются
        # несколько вкладок/устройств одного пользователя).
        count = await self._presence_enter()
        if count == 1:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user.status",
                    "user_id": str(self.user.id),
                    "status": "online",
                },
            )

        # Подключившемуся клиенту — снимок: кто из участников чата уже онлайн
        await self.send_json(
            {
                "type": "initial_presence",
                "user_ids": await self._online_member_ids(),
            }
        )

    async def disconnect(self, close_code):
        # Обновляем last_seen при отключении
        if not isinstance(self.user, AnonymousUser):
            # Offline анонсируется только когда закрылось последнее соединение
            count = await self._presence_leave()
            if count == 0:
                await self._update_last_seen()

                # Уведомляем об оффлайне
                if hasattr(self, "group_name"):
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            "type": "user.status",
                            "user_id": str(self.user.id),
                            "status": "offline",
                        },
                    )

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Обработка входящего сообщения от клиента"""
        # Перепроверка участия: пользователя могли удалить из чата после connect
        if not await self._check_membership():
            await self.close(code=4003)
            return

        text = content.get("text", "").strip()
        if not text:
            await self.send_json({"error": "Сообщение не может быть пустым"})
            return

        if len(text) > 5000:
            await self.send_json({"error": "Сообщение слишком длинное (макс. 5000)"})
            return

        # Сохраняем в БД
        message = await self._save_message(text)

        # Broadcast всем в группе
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "message": message,
            },
        )

    # --- Handlers для group_send ---

    async def chat_message(self, event):
        """Получение broadcast-сообщения и отправка клиенту"""
        await self.send_json(event["message"])

    async def user_status(self, event):
        """Получение обновления статуса пользователя"""
        await self.send_json(
            {
                "type": "user_status",
                "user_id": event["user_id"],
                "status": event["status"],
            }
        )

    async def messages_read(self, event):
        """Уведомление о прочтении сообщений"""
        await self.send_json(
            {
                "type": "messages_read",
                "reader_id": event["reader_id"],
            }
        )

    async def member_removed(self, event):
        """Участник удалён из чата: закрываем сокет удалённого пользователя."""
        if event.get("user_id") == str(self.user.id):
            await self.close(code=4003)

    # --- DB operations (sync → async safe) ---

    @database_sync_to_async
    def _check_membership(self):
        return Membership.objects.filter(chat_id=self.chat_id, user=self.user).exists()

    @database_sync_to_async
    def _save_message(self, text: str) -> dict:
        msg = Message.objects.create(chat_id=self.chat_id, sender=self.user, text=text)
        return message_payload(msg)

    @database_sync_to_async
    def _mark_messages_read(self):
        updated = (
            Message.objects.filter(
                chat_id=self.chat_id,
                is_read=False,
            )
            .exclude(sender=self.user)
            .update(is_read=True)
        )
        return updated > 0

    @database_sync_to_async
    def _update_last_seen(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.filter(id=self.user.id).update(last_seen=timezone.now())

    # --- Presence (Redis: hash user_id → счётчик активных соединений) ---

    async def _presence_enter(self) -> int:
        self._presence_entered = True
        count = await get_redis().hincrby(PRESENCE_KEY, str(self.user.id), 1)
        return int(count)

    async def _presence_leave(self) -> int:
        # Если соединение закрылось до accept (4001/4003), счётчик не трогали
        if not getattr(self, "_presence_entered", False):
            return 1
        uid = str(self.user.id)
        r = get_redis()
        count = int(await r.hincrby(PRESENCE_KEY, uid, -1))
        if count <= 0:
            await r.hdel(PRESENCE_KEY, uid)
            return 0
        return count

    @database_sync_to_async
    def _member_ids(self) -> list:
        return [
            str(uid)
            for uid in Membership.objects.filter(chat_id=self.chat_id).values_list(
                "user_id", flat=True
            )
        ]

    async def _online_member_ids(self) -> list:
        presence = await get_redis().hgetall(PRESENCE_KEY)
        members = await self._member_ids()
        return [uid for uid in members if int(presence.get(uid, 0)) > 0]
