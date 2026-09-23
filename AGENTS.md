# AGENTS.md — Контекст для AI-ассистентов и инженеров

> Этот файл содержит структурную информацию о проекте для быстрого онбординга.
> Обновлять при каждом значимом изменении архитектуры.

## 🏗 Архитектура проекта

Монорепозиторий: Django-бэкенд **в корне репозитория**, Vue-фронтенд — в `frontend/`.

```
lost-dream-messenger/
├── config/                        # Django project
│   ├── settings.py                # DB, MIDDLEWARE (+ LastSeenMiddleware), REST_FRAMEWORK, SIMPLE_JWT, SPECTACULAR, CHANNEL_LAYERS, CORS
│   ├── asgi.py                    # ASGI app: ProtocolTypeRouter (HTTP + WebSocket, AllowedHostsOriginValidator)
│   ├── urls.py                    # admin/ + api/v1/ → messenger.urls
│   └── wsgi.py                    # Fallback (в prod не используется, сервер — Daphne)
├── messenger/                     # Django app (единственное приложение)
│   ├── models.py                  # User, Chat, Membership, Message + кастомный UserManager
│   ├── serializers.py             # DRF-сериалайзеры + Swagger-аннотации
│   ├── views.py                   # ChatViewSet, RegisterView, UserSearchView, MeView
│   ├── consumers.py               # ChatConsumer (AsyncJsonWebsocketConsumer) + message_payload()
│   ├── activity.py                # touch_last_seen() — обновление last_seen с троттлингом 60 с
│   ├── middleware.py              # LastSeenMiddleware — активность на авторизованных REST-запросах
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
    │   ├── components/            # ChatSidebar, ChatWindow, MessageBubble, NewChatModal, GroupMembersModal
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
| `phone` как USERNAME_FIELD | Мессенджер-ориентированная идентификация; поле `username` из AbstractUser сохранено (у суперпользователя может быть пустой строкой, при регистрации через API в пустой `username` подставляется `phone`) |
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
| Presence через Redis-hash `messenger:presence` | Счётчик соединений на пользователя (несколько вкладок/устройств): `online` — при 0→1, `offline` — при 1→0; отдельный клиент от channel layer, ключ общий |
| `select_for_update` в `create_private` | Идемпотентность пары пользователей без unique-индекса (на M2M его не выразить); блокировка строк в порядке `id` исключает deadlock |
| `LastSeenMiddleware` читает `request.user` в response-фазе | DRF аутентифицирует запрос внутри view и сам пробрасывает пользователя в Django HttpRequest — до view там всегда аноним |
| `touch_last_seen()` с троттлингом 60 с | Активность пишется в БД не чаще раза в минуту; условие троттлинга продублировано в `UPDATE` на случай протухшего объекта в памяти |

## 📦 Модели данных

- **User** (`AbstractUser` + UUID PK): `phone` (unique, USERNAME_FIELD), `email`/`first_name`/`last_name` (опциональные), `last_seen` (обновляется при WS connect/disconnect, при отправке сообщения в WS и на любом авторизованном REST-запросе — с троттлингом 60 с). Кастомный `UserManager` нормализует телефон (оставляет цифры и `+`).
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
| POST | `/chats/` | Создать чат (создатель — админ; для GROUP обязателен `name`, можно передать `member_ids` — участники добавляются атомарно в транзакции; ответ — формат ChatDetail) |
| GET | `/chats/{id}/` | Детали чата: `members` с флагом `is_admin` у каждого + `my_is_admin` текущего пользователя |
| DELETE | `/chats/{id}/` | Удалить чат вместе с сообщениями: GROUP — только админ чата, PRIVATE — любой участник; остальным участникам приходит WS-закрытие 4004 |
| POST | `/chats/private/` | Создать/найти личный чат (идемпотентно: если PRIVATE-чат, где состоят оба пользователя, уже есть — вернёт его с 200, иначе создаст с 201). Внутри `transaction.atomic()` строки обоих пользователей берутся в `select_for_update` (порядок по `id`) — параллельные запросы пары не создают дубликаты |
| GET | `/chats/{id}/messages/` | История: страница 1 = **последние** 50 сообщений (сортировка `-created_at`), внутри страницы — по возрастанию времени |
| POST | `/chats/{id}/send/` | Отправить сообщение (REST fallback) + broadcast в WS-группу `chat_{id}` |
| POST | `/chats/{id}/add-member/` | Добавить участника (только админ, **только GROUP-чаты**) |
| POST | `/chats/{id}/remove-member/` | Удалить участника / выйти самому; нельзя удалить единственного админа; опустевший чат удаляется |
| GET | `/users/search/?q=` | Поиск по телефону/first_name/last_name, исключает себя, лимит 20 |
| GET | `/docs/` | Swagger UI |
| GET | `/schema/` | OpenAPI 3.0 schema |

Общие настройки DRF: JWT-аутентификация, `IsAuthenticated` по умолчанию, `PageNumberPagination` (PAGE_SIZE=50), DjangoFilterBackend.

`ChatViewSet.http_method_names = ["get", "post", "delete"]` — PUT/PATCH отключены, поэтому переименовать GROUP-чат через API нельзя (см. «В планах»).

## 🔌 WebSocket API

| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `ws/chat/<uuid>/?token=<jwt>` | WS | Real-time чат (regex допускает только hex+дефисы) |

**События сервер → клиент:**

| type | Payload | Описание |
|------|---------|----------|
| *(нет поля type)* | `{id, chat, sender: {id, phone, first_name, last_name}, text, created_at, is_read}` | Новое сообщение (идентичный формат из WS-отправки и REST-broadcast) |
| `user_status` | `{user_id, status: "online"\|"offline"}` | Статус пользователя (фронт хранит в `onlineUsers` и показывает точку в шапке личного чата) |
| `messages_read` | `{reader_id}` | Кто-то прочитал сообщения (приходит и самому читателю — клиент обязан фильтровать по `reader_id != my_id`) |
| `initial_presence` | `{user_ids: [...]}` | При подключении: id участников чата, которые сейчас онлайн (отправляется только подключившемуся клиенту) |
| `{error: "..."}` | — | Пустое/слишком длинное сообщение |

**События клиент → сервер:**

| type | Payload | Описание |
|------|---------|----------|
| *(json)* | `{text: "..."}` | Отправка сообщения; membership перепроверяется при каждой отправке, `last_seen` отправителя обновляется с троттлингом 60 с |

**Поведение при подключении:** проверка JWT → отказ анонимам (4001) → проверка membership → отказ не-участникам (4003) → `group_add` + `accept` → отметка чужих непрочитанных как прочитанных + broadcast `messages_read` → обновление `last_seen` → presence: `HINCRBY messenger:presence {user_id} 1`, broadcast `user_status: online` **только при счётчике 1** → отправка `initial_presence` подключившемуся клиенту.

**Поведение при отключении:** `HINCRBY -1`; broadcast `user_status: offline` и обновление `last_seen` — **только при счётчике 0** (учитывается несколько вкладок/устройств). Если соединение закрыто до accept (4001/4003), счётчик не трогается.

**Удаление участника:** REST `remove-member` шлёт в группу событие `member.removed` — consumer удалённого пользователя закрывает его сокет с кодом 4003 (фронт по этому коду убирает чат из списка).

**Удаление чата:** REST `DELETE /chats/{id}/` шлёт в группу событие `chat.deleted` — все consumer'ы закрывают сокеты с кодом 4004 (фронт убирает чат из списка и показывает «Чат удалён»).

**Коды закрытия:**

| Code | Причина |
|------|---------|
| 4001 | Невалидный/отсутствующий JWT |
| 4003 | Пользователь не участник чата (в т.ч. удалён из чата во время сессии) |
| 4004 | Чат удалён |

## 🖥 Frontend (Vue 3 SPA)

- **auth.ts (Pinia)**: login/register сохраняют токены в localStorage и грузят профиль через `/auth/me/`; `getUserFromToken()` при перезагрузке восстанавливает из JWT только `id` (payload не содержит имени/телефона), полный профиль догружает `App.vue` в `onMounted`. Logout — только очистка localStorage.
- **chat.ts (Pinia)**: `loadChats()`, `selectChat()` (первая страница сообщений + `loadChatDetails()`), `loadOlderMessages()` (prepend следующей страницы; состояние `messagesPage`/`hasMoreMessages`/`isLoadingHistory`; guard от смены чата во время запроса), `addMessage()` (дедупликация по id + обновление превью в sidebar), `markAllRead()`, `removeChat()`. Presence: `onlineUsers` (Set id) + `setUserStatus()`/`setInitialPresence()`. Состояние WS: `wsStatus` (`WsStatus`, тип экспортируется и используется в useChatSocket) + `setWsStatus()` — пишет ChatWindow, отображает ChatSidebar; сбрасывается в `disconnected` в `resetMessages()`.
- **api.ts**: axios с Bearer-interceptor; при 401 — один retry через `/auth/refresh/`, при неудаче — очистка токенов и редирект на `/login`.
- **useChatSocket.ts**: подключение по `chatId` (watch, immediate), reconnect через фиксированные 2 c (кроме кодов 4001/4003/4004), `sendMessage()` возвращает false если сокет не открыт — вызывающий код уходит в REST fallback. Колбэки: `onMessage`, `onUserStatus`, `onMessagesRead`, `onInitialPresence`, `onClose(code)`. После reconnect история НЕ перечитывается.
- **ChatWindow.vue**: отправка (WS → fallback REST `POST /send/`, при ошибке текст возвращается в input); автоскролл по id **последнего** сообщения (догрузка истории его не сбрасывает); infinite scroll вверх (`scrollTop < 100` → `loadOlderMessages()` + якорь `scrollTop += Δ scrollHeight`); шапка: название чата, presence-точка собеседника (PRIVATE) под названием, кнопка «Участники (N)» (GROUP) справа; статус **WS-соединения** пробрасывается в store (`setWsStatus`) и показывается в сайдбаре; обработка `messages_read` с фильтром по `readerId`; при close-кодах 4003/4004 — `removeChat()` + плашка («Вы удалены из этого чата» / «Чат удалён»).
- **ChatSidebar.vue**: список чатов (имя + превью последнего сообщения), кнопка «+ Новый чат», logout. В шапке рядом с приветствием — индикатор состояния **WS-соединения** текущего чата (точка + «на связи» / «подключение...» / «нет соединения»), отображается только когда чат выбран.
- **GroupMembersModal.vue**: список участников (бейджи «админ»/«вы»); админ — debounced-поиск и добавление (`POST add-member/`), удаление любого (`POST remove-member/`); любой участник — «Выйти» (выход из чата, при опустевшем чате сервер его удаляет).
- **NewChatModal.vue**: режимы «Личный / Групповой». Личный: debounced-поиск (300 мс) → `POST /chats/private/` → обновление списка + **автовыбор** чата. Групповой: название + мультивыбор пользователей из поиска (chips) → `POST /chats/ {type, name, member_ids}` → автовыбор.
- **LoginView.vue**: вход и регистрация в одной форме. Email/имя/фамилия необязательны — пустые значения вырезаются из payload перед `POST /auth/register/` (бэкенд трактует `""` как невалидный email).
- Роуты: `/login`, `/` (requiresAuth), catch-all → `/login`.

## 🐳 Инфраструктура

- **docker-compose.yml**: сервисы `db` (postgres:18, порт на хосте **5434**, healthcheck), `redis` (7-alpine, healthcheck, порт 6379), `backend` (build из корневого Dockerfile; команда: migrate → collectstatic → daphne; bind-mount `.:/app`; volume `media_data`), `frontend` (target `dev`, bind-mount исходников для HMR). **Сервис называется `backend`, не `web`.**
- **Dockerfile (backend)**: python:3.13-slim, multi-stage (pip `--prefix=/install`), непривилегированный `appuser`.
- **Dockerfile (frontend)**: node:22-alpine, `npm ci`; target `dev` — Vite с `--host 0.0.0.0`; target `prod` — билд + nginx с `nginx.conf` (upstream `backend:8000`).
- **`.dockerignore`** (корневой, для образа backend): исключает `.git`, `.env*`, `.venv/`, кэши (`.ruff_cache/`, `.pytest_cache/`, `.mypy_cache/`), `frontend/` (у фронтенда собственный build-контекст `./frontend`), `node_modules/`, `media/`, `staticfiles/`.
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
- [x] Визуальный онлайн-статус собеседника (presence в Redis + `initial_presence` + точка в шапке PRIVATE-чата)
- [x] Создание групповых чатов из UI (режим «Групповой» в NewChatModal, `member_ids` в `POST /chats/`)
- [x] Добавление/удаление участников группового чата из UI (GroupMembersModal, выход из чата, live-закрытие сокета удалённого участника)
- [x] Пагинация сообщений в UI (infinite scroll вверх с якорем позиции)
- [ ] Перечитывание истории после WS-reconnect
- [ ] Удаление чата из UI (бэкенд `DELETE /chats/{id}/` с правами и WS-закрытием 4004 готов, на фронте нет кнопки)
- [ ] Переименование GROUP-чата (нужен PATCH/PUT или отдельный action — сейчас `http_method_names` без них)
- [ ] Typing indicators («печатает...»)
- [ ] Загрузка файлов и изображений (MEDIA_* в settings заданы, но media не раздаётся)
- [ ] Message editing / deletion
- [ ] Push notifications
- [ ] Онлайн-статус участников в групповых чатах (сейчас presence показывается только в PRIVATE)

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
4. **`is_read` глобальный на сообщение** — в групповом чате прочтение одним участником помечает сообщение прочитанным для всех.
5. **Нет soft-delete** — удаление чата/сообщения физическое.
6. **Валидация пароля отключена** — `validate_password` и `min_length` в RegisterSerializer закомментированы; `AUTH_PASSWORD_VALIDATORS` в DRF не применяются автоматически.
7. **requirements.txt**: gunicorn не используется (сервер — Daphne), ruff — dev-инструмент в prod-образе.
8. **`MAILERS` в settings.py** — несуществующая настройка Django (мертвый код).
9. **Concurrent 401** — interceptor в api.ts не блокирует параллельные refresh-запросы (ротация refresh-токенов не включена, поэтому не критично).
10. **`create_private` полагается на `select_for_update`** — защита от дубликатов работает только на Postgres; на SQLite (например, в будущих тестах) запрос упадёт с `NotSupportedError`.
