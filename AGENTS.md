# AGENTS.md — Контекст для AI-ассистентов и инженеров

> Этот файл содержит структурную информацию о проекте для быстрого онбординга.
> Обновлять при каждом значимом изменении архитектуры.

## 🏗 Архитектура проекта

```
messenger/                        # Монорепозиторий
├── backend/                      # Django API + WebSocket
│   ├── config/                   # Django project settings
│   │   ├── settings.py           # DB, REST_FRAMEWORK, SPECTACULAR, JWT, CHANNEL_LAYERS, CORS
│   │   ├── asgi.py               # ASGI app (HTTP + WebSocket routing)
│   │   ├── urls.py               # Root URL config
│   │   └── wsgi.py               # WSGI fallback (не используется в prod)
│   ├── messenger/                # Основное приложение
│   │   ├── models.py             # User, Chat, Membership, Message
│   │   ├── serializers.py        # DRF сериалайзеры + Swagger-аннотации
│   │   ├── views.py              # ViewSets, RegisterView, UserSearchView
│   │   ├── consumers.py          # ChatConsumer (async WebSocket)
│   │   ├── ws_auth.py            # JWT-аутентификация для WebSocket
│   │   ├── routing.py            # WebSocket URL patterns
│   │   ├── mixins.py             # ChatMembershipMixin
│   │   ├── admin.py              # Django Admin с inlines
│   │   ├── urls.py               # Router + custom endpoints + schema
│   │   └── templates/messenger/  # Legacy embedded dev client (deprecated)
│   ├── Dockerfile                # Python 3.12-slim + Daphne
│   └── requirements.txt          # Django, DRF, Channels, channels_redis
├── frontend/                     # Vue 3 SPA
│   ├── src/
│   │   ├── assets/styles.css     # Глобальные стили (CSS variables)
│   │   ├── components/           # ChatSidebar, ChatWindow, MessageBubble, NewChatModal
│   │   ├── composables/          # useChatSocket (WebSocket composable)
│   │   ├── stores/               # Pinia: auth.ts, chat.ts
│   │   ├── services/api.ts       # Axios instance + interceptors
│   │   ├── views/                # LoginView, ChatView
│   │   ├── router/index.ts       # Vue Router + navigation guards
│   │   ├── App.vue
│   │   └── main.ts
│   ├── vite.config.ts            # Vite + proxy (/api → :8000, /ws → :8000)
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yml            # web + postgres + redis
├── .env                          # Secrets (НЕ в git)
└── .gitignore
```

## 🔑 Ключевые архитектурные решения

| Решение | Обоснование |
|---------|-------------|
| UUID PK во всех моделях | Безопасность (нет enumeration), совместимость с distributed |
| `phone` как USERNAME_FIELD | Мессенджер-ориентированная идентификация |
| Промежуточная модель Membership | Расширяемость (роли, mute, ban) без изменения основных моделей |
| Daphne вместо Gunicorn | Единый ASGI-сервер для HTTP + WebSocket |
| Redis Pub/Sub channel layer | Устойчив к таймаутам на Docker Desktop (в отличие от BRPOP core) |
| JWT через query string в WS | WebSocket не поддерживает HTTP-заголовки при handshake |
| Vite proxy вместо django-cors-headers | Zero CORS в dev, бэкенд не знает о фронтенде |
| Zustand → Pinia | Нативный state management для Vue 3, DevTools поддержка |
| @vueuse/core useDebounceFn | Готовые composables вместо самописных решений |
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
- Docker Compose (web + postgres + redis)
- Daphne ASGI server (HTTP + WebSocket)
- Redis Pub/Sub channel layer (`channels_redis.pubsub`)
- WhiteNoise для статики (Django admin, legacy client)
- Swagger UI + drf-spectacular
- Vite dev server с proxy

## 🚧 В планах (приоритет по убыванию)

### Phase 2: Features
- [ ] Визуальный онлайн-статус собеседника в шапке чата
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
- [ ] Nginx reverse proxy + SSL
- [ ] Production Docker build для frontend

## ⚠️ Известные ограничения / Tech Debt

1. **Нет rate limiting** — API и WS открыты для abuse
2. **Нет тестов** — покрытие 0% (backend + frontend)
3. **SECRET_KEY insecure** — дефолтное значение, менять перед деплоем
4. **Read receipts per-chat** — нет per-message подтверждения доставки
5. **Онлайн-статусы только в console.log** — нет визуального индикатора в UI
6. **Нет soft-delete** — удаление чата/сообщения физическое
7. **last_seen обновляется при connect/disconnect** — не отражает реальную активность
8. **Legacy embedded chat.html** — сохранён но не развивается, удалить после стабилизации SPA
9. **Нет production build для frontend** — только dev mode через Vite

## 🔧 Команды разработки

```bash
# Backend
docker compose up --build -d
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py shell_plus
docker compose logs -f web

# Frontend
cd frontend
npm install
npm run dev          # Dev server на :5173 с proxy на :8000
npm run build        # Production build → dist/
npm run preview      # Preview production build

# Полный сброс БД
docker compose down -v && docker compose up --build -d

# Проверка подключения к БД
docker compose exec web python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db import connection
print(connection.cursor().execute('SELECT version()').fetchone())
"
