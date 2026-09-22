# AGENTS.md — Контекст для AI-ассистентов и инженеров

> Этот файл содержит структурную информацию о проекте для быстрого онбординга.
> Обновлять при каждом значимом изменении архитектуры.

## 🏗 Архитектура проекта

```
messenger/                        # Монорепозиторий
├── backend/                      # Django API + WebSocket
│   ├── config/
│   │   ├── settings.py           # DB, REST_FRAMEWORK, SPECTACULAR, JWT, CHANNEL_LAYERS
│   │   ├── asgi.py               # ASGI app (HTTP + WebSocket routing)
│   │   ├── urls.py
│   │   └── wsgi.py               # Fallback (не используется в prod)
│   ├── messenger/
│   │   ├── models.py             # User, Chat, Membership, Message
│   │   ├── serializers.py        # DRF сериалайзеры + Swagger-аннотации
│   │   ├── views.py              # ViewSets, RegisterView, UserSearchView
│   │   ├── consumers.py          # ChatConsumer (async WebSocket)
│   │   ├── ws_auth.py            # JWT-аутентификация для WebSocket
│   │   ├── routing.py            # WebSocket URL patterns
│   │   ├── mixins.py             # ChatMembershipMixin
│   │   ├── admin.py              # Django Admin с inlines
│   │   ├── urls.py               # Router + custom endpoints + schema
│   │   └── templates/messenger/  # Legacy embedded client (deprecated)
│   ├── Dockerfile                # Python 3.12-slim + Daphne
│   └── requirements.txt
├── frontend/                     # Vue 3 SPA
│   ├── src/
│   │   ├── assets/styles.css     # Глобальные стили (CSS variables)
│   │   ├── components/           # ChatSidebar, ChatWindow, MessageBubble, NewChatModal
│   │   ├── composables/          # useChatSocket
│   │   ├── stores/               # Pinia: auth.ts, chat.ts
│   │   ├── services/api.ts       # Axios instance + interceptors
│   │   ├── views/                # LoginView, ChatView
│   │   ├── router/index.ts       # Vue Router + navigation guards
│   │   ├── App.vue
│   │   └── main.ts
│   ├── vite.config.ts            # Vite + proxy (/api, /ws → backend:8000)
│   ├── nginx.conf                # Prod: статика + reverse proxy API/WS
│   ├── Dockerfile                # Multi-stage: dev (Vite) / prod (nginx)
│   └── package.json
├── docker-compose.yml            # backend + frontend + postgres + redis
├── .env
└── .gitignore
```

## 🔑 Ключевые архитектурные решения

| Решение | Обоснование |
|---------|-------------|
| UUID PK во всех моделях | Безопасность (нет enumeration), совместимость с distributed |
| /auth/me/ вместо search по себе | Надёжное получение профиля без зависимости от search-эндпоинта |
| `phone` как USERNAME_FIELD | Мессенджер-ориентированная идентификация |
| Промежуточная модель Membership | Расширяемость (роли, mute, ban) без изменения основных моделей |
| Daphne вместо Gunicorn | Единый ASGI-сервер для HTTP + WebSocket |
| Redis Pub/Sub channel layer | Устойчив к таймаутам на Docker Desktop (в отличие от BRPOP core) |
| JWT через query string в WS | WebSocket не поддерживает HTTP-заголовки при handshake |
| Vite proxy вместо django-cors-headers | Zero CORS в dev, бэкенд не знает о фронтенде |
| Pinia для state management | Нативный store для Vue 3, DevTools поддержка |
| @vueuse/core | Готовые composables (useDebounceFn) вместо самописных решений |
| Multi-stage Dockerfile frontend | Dev (Vite HMR) и prod (nginx) из одного Dockerfile |
| Embedded chat.html (legacy) | Сохранён для быстрой отладки API, не развивается |

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
| GET | /auth/me/ | Профиль текущего пользователя (по JWT) |
| GET | `/chats/` | Мои чаты с last_message |
| POST | `/chats/` | Создать групповой чат |
| POST | `/chats/private/` | Создать/найти личный чат (идемпотентно) |
| GET | `/chats/{id}/` | Детали чата с участниками |
| GET | `/chats/{id}/messages/` | История с пагинацией |
| POST | `/chats/{id}/send/` | Отправить сообщение (REST fallback) |
| POST | `/chats/{id}/add-member/` | Добавить участника (admin only) |
| POST | `/chats/{id}/remove-member/` | Удалить участника / выйти |
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

### Frontend (Vue 3 SPA)

- Auth flow (login/register/logout) с JWT restore из localStorage
- Protected routes через Vue Router navigation guard
- Chat sidebar со списком чатов и превью последнего сообщения
- Chat window с real-time сообщениями через WebSocket
- Read receipts (✓ серая / ✓✓ зелёная)
- Индикатор WS-соединения в шапке чата
- Создание личного чата через модалку с debounced поиском пользователей
- Авто-reconnect WebSocket с backoff
- REST fallback при отправке если WS недоступен
- Vite proxy для CORS-free разработки

### Инфраструктура
- Docker Compose (backend + frontend + postgres + redis)
- Daphne ASGI server (HTTP + WebSocket)
- Redis Pub/Sub channel layer (`channels_redis.pubsub`)
- WhiteNoise для статики (Django admin, legacy client)
- Swagger UI + drf-spectacular
- Vite dev server с proxy на backend
- Nginx для production-раздачи frontend + reverse proxy API/WS

### Frontend (Vue 3 SPA)
- Auth flow (login/register/logout) с JWT restore из localStorage
- Protected routes через Vue Router navigation guard
- Chat sidebar со списком чатов и превью последнего сообщения
- Chat window с real-time сообщениями через WebSocket
- Read receipts (✓ серая / ✓✓ зелёная)
- Индикатор WS-соединения в шапке чата
- Создание личного чата через модалку с debounced поиском пользователей
- Авто-reconnect WebSocket с backoff
- REST fallback при отправке если WS недоступен
- Vite proxy для CORS-free разработки
- Docker: dev (Vite HMR) + prod (nginx)

## 🚧 В планах (приоритет по убыванию)

### Phase 2: Features
- [ ] Создание групповых чатов из UI
- [ ] Добавление участников в групповой чат из UI
- [ ] Пагинация сообщений (scroll up → загрузить ещё)
- [ ] Typing indicators («печатает...»)
- [ ] Загрузка файлов и изображений
- [ ] Message editing / deletion
- [ ] Push notifications

### Phase 3: Quality & Ops
- [ ] pytest + factory_boy + coverage > 80%
- [ ] Vitest для frontend unit-тестов
- [ ] Pre-commit hooks (ruff, mypy, eslint)
- [ ] CI/CD (GitHub Actions)
- [ ] Rate limiting (django-ratelimit)
- [ ] Logging + Sentry
- [ ] Production deploy (nginx + SSL)

## ⚠️ Известные ограничения / Tech Debt

1. **Нет rate limiting** — API и WS открыты для abuse
2. **Нет тестов** — покрытие 0% (backend + frontend)
3. **SECRET_KEY insecure** — дефолтное значение, менять перед деплоем
4. **Read receipts per-chat** — нет per-message подтверждения доставки
5. **Нет soft-delete** — удаление чата/сообщения физическое
6. **last_seen обновляется при connect/disconnect** — не отражает реальную активность
7. **Нет production build для frontend** — только dev mode через Vite

## 🔧 Команды разработки

```bash
# Backend
docker compose up --build -d
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py shell_plus
docker compose logs -f

# Полный сброс БД
docker compose down -v && docker compose up --build -d
```
