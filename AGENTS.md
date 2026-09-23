# AGENTS.md — Контекст для AI-ассистентов и инженеров

> Этот файл содержит структурную информацию о проекте для быстрого онбординга.
> Обновлять при каждом значимом изменении архитектуры.

## 🏗 Архитектура проекта

Монорепозиторий: Django-бэкенд **в корне репозитория**, Vue-фронтенд — в `frontend/`.

```
lost-dream-messenger/
├── config/                        # Django project
│   ├── settings.py                # DB, REST_FRAMEWORK, SIMPLE_JWT, SPECTACULAR, CHANNEL_LAYERS, CORS
│   ├── asgi.py                    # ASGI app: ProtocolTypeRouter (HTTP + WebSocket, AllowedHostsOriginValidator)
│   ├── urls.py                    # admin/ + api/v1/ → messenger.urls
│   └── wsgi.py                    # Fallback (в prod не используется, сервер — Daphne)
├── messenger/                     # Django app (единственное приложение)
│   ├── models.py                  # User, Chat, Membership, Message + кастомный UserManager
│   ├── serializers.py             # DRF-сериалайзеры + Swagger-аннотации
│   ├── views.py                   # ChatViewSet, RegisterView, UserSearchView, MeView
│   ├── consumers.py               # ChatConsumer (AsyncJsonWebsocketConsumer) + message_payload()
│   ├── ws_auth.py                 # JWT-аутентификация для WebSocket (token из query string)
│   ├── routing.py                 # WebSocket URL patterns
│   ├── admin.py                   # Django Admin с inlines (Membership, последние сообщения)
│   ├── urls.py                    # DefaultRouter (chats) + auth/users/schema/docs
│   ├── migrations/
│   └── tests.py                   # Пусто — тестов нет
├── manage.py
├── requirements.txt               # Пины версий (prod + dev-инструменты, см. Tech Debt)
├── Dockerfile                     # Python 3.13-slim, multi-stage, непривилегированный appuser, Daphne
├── docker-compose.yml             # db (postgres:18) + redis:7 + backend + frontend (Vite dev)
├── .env / .env.example            # DB_* читаются settings.py; DJANGO_SECRET_KEY/DEBUG — НЕ читаются
└── frontend/                      # Vue 3 SPA
    ├── src/
    │   ├── assets/styles.css      # Глобальные стили (CSS variables)
    │   ├── components/            # ChatSidebar, ChatWindow, MessageBubble, NewChatModal
    │   │   └── (TheWelcome, WelcomeItem, icons/ — мёртвый код шаблона create-vue)
    │   ├── composables/           # useChatSocket — WS-подключение, reconnect, отправка
    │   ├── stores/                # Pinia: auth.ts (JWT, профиль), chat.ts (чаты, сообщения)
    │   ├── services/api.ts        # Axios instance + interceptors (Bearer, авто-refresh при 401)
    │   ├── views/                 # LoginView, ChatView
    │   ├── router/index.ts        # Vue Router + navigation guard (requiresAuth)
    │   ├── App.vue                # При старте догружает профиль через /auth/me/
    │   └── main.ts
    ├── vite.config.ts             # Proxy /api и /ws → http://backend:8000 (Docker DNS)
    ├── nginx.conf                 # Prod: SPA fallback + proxy /api и /ws → backend:8000
    ├── Dockerfile                 # node:22-alpine; targets: dev (Vite) / prod (nginx)
    └── package.json               # engines: node ^22.18 || >=24.12
```

## 🔑 Ключевые архитектурные решения

| Решение | Обоснование |
|---------|-------------|
| UUID PK во всех моделях | Безопасность (нет enumeration), совместимость с distributed |
| `phone` как USERNAME_FIELD | Мессенджер-ориентированная идентификация; поле `username` из AbstractUser сохранено (у суперпользователя может быть пустой строкой) |
| `/auth/me/` для профиля | JWT payload содержит только `user_id` — профиль всегда догружается отдельным запросом |
| Промежуточная модель Membership | Расширяемость (роли, mute, ban); `is_admin` управляет add/remove member |
| Daphne вместо Gunicorn | Единый ASGI-сервер для HTTP + WebSocket |
| Redis Pub/Sub channel layer | `channels_redis.pubsub` устойчив к таймаутам на Docker Desktop (в отличие от BRPOP core) |
| JWT через query string в WS | WebSocket не поддерживает HTTP-заголовки при handshake |
| Vite proxy + django-cors-headers | Proxy даёт zero-CORS в dev; corsheaders установлен как страховка для прямых запросов (CORS_ALLOWED_ORIGINS: localhost:5173) |
| Pinia для state management | Нативный store для Vue 3, DevTools поддержка |
| @vueuse/core | Готовые composables (useDebounceFn) вместо самописных |
| Multi-stage Dockerfile frontend | Dev (Vite HMR) и prod (nginx) из одного Dockerfile; в compose пока используется только dev |
| `message_payload()` в consumers.py | Единый формат WS-сообщения для consumer'а и REST-broadcast — клиенты не различают источник |

## 📦 Модели данных

- **User** (`AbstractUser` + UUID PK): `phone` (unique, USERNAME_FIELD), `email`/`first_name`/`last_name` (опциональные), `last_seen` (обновляется при WS connect/disconnect). Кастомный `UserManager` нормализует телефон (оставляет цифры и `+`).
- **Chat**: `type` (PRIVATE/GROUP), `name` (для групп), `members` M2M через Membership, ordering `-created_at`.
- **Membership**: user ↔ chat, `is_admin`, unique constraint `unique_user_chat` (продублирован legacy `unique_together`).
- **Message**: `chat` FK, `sender` FK, `text` (≤5000), `created_at`, `is_read` (глобальный флаг на сообщение, не per-user), index `(chat, created_at)`, ordering `created_at`.

## 🔌 REST API (префикс `/api/v1/`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register/` | Регистрация (phone, password, password_confirm; email/name опциональны) + JWT в ответе |
| POST | `/auth/login/` | JWT token pair (поле `phone`, не `username`) |
| POST | `/auth/refresh/` | Refresh access token |
| GET | `/auth/me/` | Профиль текущего пользователя (по JWT) |
| GET | `/chats/` | Мои чаты с `last_message` и `interlocutor` (для PRIVATE), пагинация (50) |
| POST | `/chats/` | Создать чат (создатель автоматически становится админом через Membership) |
| GET | `/chats/{id}/` | Детали чата с участниками |
| DELETE | `/chats/{id}/` | Удалить чат (⚠️ доступен любому участнику — см. Tech Debt) |
| POST | `/chats/private/` | Создать/найти личный чат (идемпотентно: ищет PRIVATE-чат с ровно 2 участниками) |
| GET | `/chats/{id}/messages/` | История: страница 1 = **последние** 50 сообщений (сортировка `-created_at`), внутри страницы — по возрастанию времени |
| POST | `/chats/{id}/send/` | Отправить сообщение (REST fallback) + broadcast в WS-группу `chat_{id}` |
| POST | `/chats/{id}/add-member/` | Добавить участника (только админ, **только GROUP-чаты**) |
| POST | `/chats/{id}/remove-member/` | Удалить участника / выйти самому; нельзя удалить единственного админа; опустевший чат удаляется |
| GET | `/users/search/?q=` | Поиск по телефону/first_name/last_name, исключает себя, лимит 20 |
| GET | `/docs/` | Swagger UI |
| GET | `/schema/` | OpenAPI 3.0 schema |

Общие настройки DRF: JWT-аутентификация, `IsAuthenticated` по умолчанию, `PageNumberPagination` (PAGE_SIZE=50), DjangoFilterBackend.

## 🔌 WebSocket API

| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `ws/chat/<uuid>/?token=<jwt>` | WS | Real-time чат (regex допускает только hex+дефисы) |

**События сервер → клиент:**

| type | Payload | Описание |
|------|---------|----------|
| *(нет поля type)* | `{id, chat, sender: {id, phone, first_name, last_name}, text, created_at, is_read}` | Новое сообщение (идентичный формат из WS-отправки и REST-broadcast) |
| `user_status` | `{user_id, status: "online"\|"offline"}` | Статус пользователя (фронт пока только логирует) |
| `messages_read` | `{reader_id}` | Кто-то прочитал сообщения (приходит и самому читателю — клиент обязан фильтровать по `reader_id != my_id`) |
| `{error: "..."}` | — | Пустое/слишком длинное сообщение |

**События клиент → сервер:**

| type | Payload | Описание |
|------|---------|----------|
| *(json)* | `{text: "..."}` | Отправка сообщения; membership перепроверяется при каждой отправке |

**Поведение при подключении:** проверка JWT → отказ анонимам (4001) → проверка membership → отказ не-участникам (4003) → `group_add` + `accept` → отметка чужих непрочитанных как прочитанных + broadcast `messages_read` → обновление `last_seen` → broadcast `user_status: online`.

**Коды закрытия:**

| Code | Причина |
|------|---------|
| 4001 | Невалидный/отсутствующий JWT |
| 4003 | Пользователь не участник чата (в т.ч. удалён из чата во время сессии) |

## 🖥 Frontend (Vue 3 SPA)

- **auth.ts (Pinia)**: login/register сохраняют токены в localStorage и грузят профиль через `/auth/me/`; `getUserFromToken()` при перезагрузке восстанавливает из JWT только `id` (payload не содержит имени/телефона), полный профиль догружает `App.vue` в `onMounted`. Logout — только очистка localStorage.
- **chat.ts (Pinia)**: `loadChats()`, `selectChat()` (загружает первую страницу сообщений), `addMessage()` (дедупликация по id + обновление превью в sidebar), `markAllRead()`.
- **api.ts**: axios с Bearer-interceptor; при 401 — один retry через `/auth/refresh/`, при неудаче — очистка токенов и редирект на `/login`.
- **useChatSocket.ts**: подключение по `chatId` (watch, immediate), reconnect через фиксированные 2 c (кроме кодов 4001/4003), `sendMessage()` возвращает false если сокет не открыт — вызывающий код уходит в REST fallback. После reconnect история НЕ перечитывается.
- **ChatWindow.vue**: отправка (WS → fallback REST `POST /send/`), автоскролл, индикатор состояния **WS-соединения** (не присутствия собеседника!), обработка `messages_read` с фильтром по `readerId`.
- **NewChatModal.vue**: debounced-поиск (300 мс) → `POST /chats/private/` → обновление списка чатов (созданный чат не выбирается автоматически).
- Роуты: `/login`, `/` (requiresAuth), catch-all → `/login`.

## 🐳 Инфраструктура

- **docker-compose.yml**: сервисы `db` (postgres:18, порт на хосте **5434**, healthcheck), `redis` (7-alpine, healthcheck, порт 6379), `backend` (build из корневого Dockerfile; команда: migrate → collectstatic → daphne; bind-mount `.:/app`; volume `media_data`), `frontend` (target `dev`, bind-mount исходников для HMR). **Сервис называется `backend`, не `web`.**
- **Dockerfile (backend)**: python:3.13-slim, multi-stage (pip `--prefix=/install`), непривилегированный `appuser`.
- **Dockerfile (frontend)**: node:22-alpine, `npm ci`; target `dev` — Vite с `--host 0.0.0.0`; target `prod` — билд + nginx с `nginx.conf` (upstream `backend:8000`).
- Статика: WhiteNoise (`CompressedManifestStaticFilesStorage`), `collectstatic` выполняется в команде compose.
- Swagger UI + drf-spectacular с JWT security scheme и persistAuthorization.

## 🔧 Команды разработки

```bash
# Поднять всё
docker compose up --build -d

# Миграции / админка / shell (сервис — backend!)
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py shell
docker compose logs -f

# Frontend локально (вне Docker): proxy ожидает хост `backend`,
# поэтому npm run dev имеет смысл только внутри compose
cd frontend && npm ci && npm run dev        # Vite
cd frontend && npm run type-check           # vue-tsc
cd frontend && npm run build                # type-check + vite build

# Линт бэкенда (ruff установлен в requirements)
ruff check .

# Полный сброс БД
docker compose down -v && docker compose up --build -d
```

## 🚧 В планах (приоритет по убыванию)

### Phase 2: Features
- [ ] Визуальный онлайн-статус собеседника (события `user_status` с сервера уже есть, нужен UI + состояние в store)
- [ ] Создание групповых чатов из UI
- [ ] Добавление/удаление участников группового чата из UI
- [ ] Пагинация сообщений в UI (scroll up → загрузить ещё; API уже отдаёт страницы от новых к старым)
- [ ] Перечитывание истории после WS-reconnect
- [ ] Typing indicators («печатает...»)
- [ ] Загрузка файлов и изображений (MEDIA_* в settings заданы, но media не раздаётся)
- [ ] Message editing / deletion
- [ ] Push notifications

### Phase 3: Quality & Ops
- [ ] pytest + factory_boy + coverage > 80% (tests.py сейчас пустой)
- [ ] Vitest для frontend unit-тестов
- [ ] ESLint/Prettier + pre-commit hooks (ruff для backend уже есть)
- [ ] CI/CD (GitHub Actions)
- [ ] Rate limiting (API и WS)
- [ ] Logging + Sentry
- [ ] Production deploy: prod-сервис frontend в compose, SSL, настройки из env

## ⚠️ Известные ограничения / Tech Debt

1. **SECRET_KEY и DEBUG захардкожены** в `settings.py`; `DJANGO_SECRET_KEY`/`DJANGO_DEBUG` из `.env.example` **не читаются** — перед деплоем перевести на env.
2. **Нет rate limiting** — API и WS открыты для abuse.
3. **Нет тестов** — покрытие 0% (backend + frontend).
4. **`DELETE /chats/{id}/` не переопределён** — любой участник (не только админ) может удалить чат; эндпоинт не задокументирован в Swagger-описаниях.
5. **`is_read` глобальный на сообщение** — в групповом чате прочтение одним участником помечает сообщение прочитанным для всех.
6. **`create_private` не атомарен** — без транзакции/unique-ограничения параллельные запросы теоретически могут создать дубликаты личных чатов.
7. **`last_seen` обновляется только при WS connect/disconnect** — не отражает реальную активность.
8. **Нет soft-delete** — удаление чата/сообщения физическое.
9. **Валидация пароля отключена** — `validate_password` и `min_length` в RegisterSerializer закомментированы; `AUTH_PASSWORD_VALIDATORS` в DRF не применяются автоматически.
10. **`.dockerignore` не исключает `.venv/` и `.ruff_cache/`** — попадают в build-контекст и образ (`COPY . .`), также в образ копируется `frontend/`.
11. **requirements.txt**: gunicorn не используется (сервер — Daphne), ruff — dev-инструмент в prod-образе.
12. **Мёртвый код фронтенда**: TheWelcome.vue, WelcomeItem.vue, icons/, шаблонный CSS в App.vue, закомментированный блок в ChatSidebar.vue, дефолтный frontend/README.md, title «Vite App» в index.html.
13. **`MAILERS` в settings.py** — несуществующая настройка Django (мертвый код); `ALLOWED_HOSTS` содержит некорректный `'localhost:5173'` (host без порта).
14. **`RegisterSerializer.validate_username`** возвращает `None` для пустой строки → потенциальный IntegrityError при регистрации с `username: ""` через API (фронт это поле не отправляет).
15. **Форма регистрации на фронте** делает email/first_name/last_name обязательными, хотя бэкенд их не требует.
16. **Concurrent 401** — interceptor в api.ts не блокирует параллельные refresh-запросы (ротация refresh-токенов не включена, поэтому не критично).
