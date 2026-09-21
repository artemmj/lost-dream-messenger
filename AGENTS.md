# AGENTS.md — Контекст для AI-ассистентов и инженеров

> Этот файл содержит структурную информацию о проекте для быстрого онбординга.
> Обновлять при каждом значимом изменении архитектуры.

## 🏗 Архитектура проекта
```
messenger/
├── config/                  # Django project settings
│   ├── settings.py          # DB, REST_FRAMEWORK, SPECTACULAR, JWT
│   ├── urls.py              # Root URL config
│   └── wsgi.py
├── messenger/               # Основное приложение
│   ├── models.py            # User, Chat, Membership, Message
│   ├── serializers.py       # DRF сериалайзеры + Swagger-аннотации
│   ├── views.py             # ViewSets, RegisterView, UserSearchView, ChatClientView
│   ├── mixins.py            # ChatMembershipMixin
│   ├── admin.py             # Django Admin с inlines
│   ├── urls.py              # Router + custom endpoints + schema
│   └── templates/
│       └── messenger/
│           └── chat.html    # Embedded Vue 3 dev client (single file)
├── docker-compose.yml       # web + postgres services
├── Dockerfile               # Multi-stage build, Python 3.12-slim
├── .env                     # Secrets (НЕ в git)
└── requirements.txt
```


## 🔑 Ключевые архитектурные решения

| Решение | Обоснование |
|---------|-------------|
| UUID PK во всех моделях | Безопасность (нет enumeration), совместимость с будущим distributed |
| `phone` как USERNAME_FIELD | Мессенджер-ориентированная идентификация |
| Промежуточная модель Membership | Расширяемость (роли, mute, ban) без изменения основных моделей |
| Embedded Vue client в Django template | Zero-build dev environment, нет CORS, быстрый feedback loop |
| `{% verbatim %}` в chat.html | Экранирование Vue {{ }} от Django template engine |
| WhiteNoise для статики | Gunicorn не отдаёт статику; WhiteNoise решает это без nginx |
| drf-spectacular вместо yasg | Поддержка DRF 3.15+, OpenAPI 3.0, активная разработка |
| Polling (2s interval) вместо WS | Временный костыль до внедрения Django Channels |

## ✅ Реализовано

### Модели
- `User` (AbstractUser + UUID + phone as username + custom UserManager + last_seen)
- `Chat` (PRIVATE / GROUP + UUID)
- `Membership` (user ↔ chat + is_admin + unique constraint)
- `Message` (text + sender FK + is_read + indexed by chat+created_at)

### REST API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register/` | Регистрация + JWT в ответе |
| POST | `/auth/login/` | JWT token pair |
| POST | `/auth/refresh/` | Refresh access token |
| GET | `/chats/` | Мои чаты с last_message |
| POST | `/chats/` | Создать групповой чат |
| POST | `/chats/private/` | Создать/найти личный чат |
| GET | `/chats/{id}/` | Детали чата |
| GET | `/chats/{id}/messages/` | История с пагинацией |
| POST | `/chats/{id}/send/` | Отправить сообщение (REST fallback) |
| POST | `/chats/{id}/add-member/` | Добавить участника (admin only) |
| POST | `/chats/{id}/remove-member/` | Удалить / выйти |
| GET | `/users/search/?q=` | Поиск по телефону/имени |
| GET | `/docs/` | Swagger UI |
| GET | `/schema/` | OpenAPI 3.0 schema |

### WebSocket API
| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `ws/chat/<uuid>/?token=<jwt>` | WS | Real-time чат |

**События сервер → клиент:**
| type | Payload | Описание |
|------|---------|----------|
| (message object) | `{id, chat, sender, text, created_at, is_read}` | Новое сообщение |
| `user_status` | `{user_id, status: "online"\|"offline"}` | Статус пользователя |
| `messages_read` | `{reader_id}` | Собеседник прочитал сообщения |

**События клиент → сервер:**
| type | Payload | Описание |
|------|---------|----------|
| (json) | `{text: "..."}` | Отправка сообщения |

**Коды закрытия:**
| Code | Причина |
|------|---------|
| 4001 | Невалидный/отсутствующий JWT |
| 4003 | Пользователь не участник чата |

### Инфраструктура
- Docker Compose (web + postgres + redis)
- Daphne ASGI server (HTTP + WebSocket)
- Redis Pub/Sub channel layer (`channels_redis.pubsub`)
- WhiteNoise для статики
- Swagger UI + drf-spectacular
- Embedded Vue 3 dev client с WebSocket поддержкой

### Dev Client Features
- Auth flow (register/login/logout) с localStorage
- Auto-refresh JWT при 401
- Real-time сообщения через WebSocket
- Авто-reconnect с backoff при разрыве
- REST fallback при отправке если WS недоступен
- Read receipts (✓ серая / ✓✓ зелёная)
- Онлайн-статусы в консоли
- Индикатор WS-соединения в шапке чата

## 🚧 В планах (приоритет по убыванию)

### Phase 3: Production Frontend
- [ ] Отдельный репозиторий: Vue 3 + Vite + TypeScript + Pinia
- [ ] Vue Router (auth / chats / profile)
- [ ] Компонентная архитектура
- [ ] Удаление embedded chat.html из Django

### Phase 4: Features
- [ ] Загрузка файлов и изображений
- [ ] Push notifications
- [ ] Message editing / deletion
- [ ] Typing indicators
- [ ] Групповые чаты: роли, mute, ban

### Phase 5: Quality & Ops
- [ ] pytest + factory_boy + coverage > 80%
- [ ] Pre-commit hooks (ruff, mypy)
- [ ] CI/CD (GitHub Actions)
- [ ] Rate limiting (django-ratelimit)
- [ ] Logging + Sentry
- [ ] Nginx reverse proxy + SSL

## ⚠️ Известные ограничения / Tech Debt

1. **Нет rate limiting** — API и WS открыты для abuse
2. **Нет тестов** — покрытие 0%
3. **SECRET_KEY в .env** — дефолтное значение insecure
4. **Embedded client** — временное решение, не масштабировать
5. **Read receipts только per-chat** — нет per-message подтверждения доставки
6. **Онлайн-статусы только в console.log** — нет визуального индикатора в UI
7. **Нет soft-delete** — удаление чата/сообщения физическое
8. **last_seen обновляется при connect/disconnect** — не отражает реальную активность

## 🔧 Команды разработки

```bash
# Запуск
docker compose up --build -d

# Миграции
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Shell
docker compose exec web python manage.py shell_plus

# Логи
docker compose logs -f web

# Полный сброс БД
docker compose down -v && docker compose up --build -d

# Проверка подключения к БД
docker compose exec web python -c "
import django; import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db import connection
print(connection.cursor().execute('SELECT version()').fetchone())
"
```
