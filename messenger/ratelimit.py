"""
Лимитеры для WebSocket: DRF-троттлинг до Channels-consumer'ов не дотягивается.

Fixed window на Redis — один вызов `INCR` + `PEXPIRE` (атомарно через Lua), O(1)
памяти и один round trip на событие. Компромисс: на границе окна возможен
всплеск до 2× лимита. Для защиты от флуда этого достаточно, скользящее окно
(ZSET с удалением старых элементов) было бы переплатой за точность.
"""

import redis.asyncio as aioredis

_INCR_WITH_TTL = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RedisWindowLimiter:
    """Счётчик событий в фиксированном окне. Ключ задаёт вызывающий код — так
    лимитер переиспользуется и для сообщений, и для подключений."""

    def __init__(self, limit: int, window_s: int):
        self.limit = limit
        self.window_ms = window_s * 1000
        self._script = None

    async def hit(self, client: aioredis.Redis, key: str) -> int:
        """Номер текущего события в окне: 1 — первое, limit + 1 — уже перебор."""
        if self._script is None:
            self._script = client.register_script(_INCR_WITH_TTL)
        return int(await self._script(keys=[key], args=[self.window_ms]))


# Сообщения: того же порядка, что REST-scope `send` (60/min). Смысл в том, чтобы
# лимит нельзя было обойти, закрыв сокет и уйдя в REST-fallback.
MESSAGE_LIMITER = RedisWindowLimiter(limit=10, window_s=10)

# Подключения: reconnect-шторм опасен не самим handshake, а тем, что каждое
# подключение отмечает чужие сообщения прочитанными и делает broadcast всей группе.
CONNECT_LIMITER = RedisWindowLimiter(limit=20, window_s=60)

# Presence-счётчик (messenger:presence) уже считает активные соединения
# пользователя — используем его же как кап, отдельного учёта не заводим.
MAX_CONNECTIONS_PER_USER = 5
