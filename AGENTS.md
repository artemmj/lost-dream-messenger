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
- `User` (AbstractUser + UUID + phone as username + custom UserManager)
- `Chat` (PRIVATE / GROUP + UUID)
- `Membership` (user ↔ chat + is_admin + unique constraint)
- `Message` (text + sender FK + is_read + indexed by chat+created_at)

### 📡 API Endpoints (Detailed)

> Base URL: `/api/v1`  
> Auth: `Bearer <access_token>` (кроме `/auth/*` и `/docs/`)  
> Content-Type: `application/json`  
> Pagination: `PageNumberPagination`, `page_size=50`, response wrapper: `{ count, next, previous, results }`

### Auth

#### `POST /auth/register/`
Регистрация нового пользователя. Возвращает JWT сразу после создания.

| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| → Request | `phone` | string | ✅ | Уникальный номер телефона |
| → Request | `email` | string | ✅ | Нормализуется в lowercase |
| → Request | `first_name` | string | ✅ | |
| → Request | `last_name` | string | ✅ | |
| → Request | `password` | string | ✅ | Мин. 8 символов, проверяется Django password validators |
| → Request | `password_confirm` | string | ✅ | Должен совпадать с `password` |
| ← Response 201 | `user.id` | UUID | | |
| ← Response 201 | `user.phone` | string | | |
| ← Response 201 | `user.email` | string | | |
| ← Response 201 | `user.first_name` | string | | |
| ← Response 201 | `user.last_name` | string | | |
| ← Response 201 | `access` | string | | JWT access token |
| ← Response 201 | `refresh` | string | | JWT refresh token |
| ← Error 400 | `{field: [errors]}` | object | | Ошибки валидации по полям |

#### `POST /auth/login/`
| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| → Request | `phone` | string | ✅ | |
| → Request | `password` | string | ✅ | |
| ← Response 200 | `access` | string | | |
| ← Response 200 | `refresh` | string | | |
| ← Error 401 | `detail` | string | | Неверные credentials |

#### `POST /auth/refresh/`
| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| → Request | `refresh` | string | ✅ | Refresh token |
| ← Response 200 | `access` | string | | Новый access token |
| ← Error 401 | `detail` | string | | Invalid/expired refresh |

---

### Chats

#### `GET /chats/`
Список чатов текущего пользователя. Оптимизирован через `prefetch_related`.

| Direction | Field | Type | Description |
|-----------|-------|------|-------------|
| ← Response | `results[].id` | UUID | |
| ← Response | `results[].type` | enum | `PRIVATE` \| `GROUP` |
| ← Response | `results[].name` | string | Название группового чата (пусто для PRIVATE) |
| ← Response | `results[].created_at` | ISO 8601 | |
| ← Response | `results[].last_message` | Message \| null | Полное сообщение или null |
| ← Response | `results[].interlocutor` | User \| null | Собеседник для PRIVATE, null для GROUP |

#### `POST /chats/`
Создание группового чата. Создатель автоматически становится админом.

| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| → Request | `name` | string | ❌ | Название чата |
| → Request | `type` | enum | ❌ | По умолчанию `GROUP` |
| ← Response 201 | ChatDetail | object | Полный объект чата |

#### `POST /chats/private/`
Создание или получение существующего личного чата. Идемпотентен.

| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| → Request | `interlocutor_id` | UUID | ✅ | ID второго участника |
| ← Response 200 | ChatDetail | object | Существующий чат найден |
| ← Response 201 | ChatDetail | object | Новый чат создан |
| ← Error 400 | `detail` | string | Нельзя с собой / пользователь не найден |

#### `GET /chats/{id}/`
Детальная информация о чате со списком участников.

| Direction | Field | Type | Description |
|-----------|-------|------|-------------|
| ← Response | `id` | UUID | |
| ← Response | `type` | enum | `PRIVATE` \| `GROUP` |
| ← Response | `name` | string | |
| ← Response | `members[]` | User[] | Список всех участников |
| ← Response | `created_at` | ISO 8601 | |

---

### Messages

#### `GET /chats/{id}/messages/`
История сообщений с пагинацией. Требует участия в чате.

| Direction | Field | Type | Description |
|-----------|-------|------|-------------|
| → Query | `page` | int | Номер страницы (optional) |
| ← Response | `results[].id` | UUID | |
| ← Response | `results[].chat` | UUID | |
| ← Response | `results[].sender` | User | Вложенный объект отправителя |
| ← Response | `results[].text` | string | Текст сообщения |
| ← Response | `results[].created_at` | ISO 8601 | |
| ← Response | `results[].is_read` | bool | Флаг прочтения |
| ← Error 403 | `detail` | string | Не участник чата |

#### `POST /chats/{id}/send/`
Отправка сообщения. `chat` и `sender` определяются автоматически.

| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| → Request | `text` | string | ✅ | 1–5000 символов, не может быть пустым |
| ← Response 201 | Message | object | Полное созданное сообщение с sender |
| ← Error 400 | `text` | array | Ошибки валидации текста |
| ← Error 403 | `detail` | string | Не участник чата |

---

### Members

#### `POST /chats/{id}/add-member/`
Добавление участника. Требуются права администратора.

| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| → Request | `user_id` | UUID | ✅ | ID добавляемого пользователя |
| ← Response 201 | `detail` | string | Подтверждение добавления |
| ← Error 400 | `detail` | string | Пользователь уже в чате / не найден |
| ← Error 403 | `detail` | string | Нет прав админа / не участник |

#### `POST /chats/{id}/remove-member/`
Удаление участника. Админ может удалять других, обычный участник — только себя.

| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| → Request | `user_id` | UUID | ✅ | ID удаляемого пользователя |
| ← Response 200 | `detail` | string | Подтверждение удаления |
| ← Response 200 | `detail` | string | «Чат удалён» если не осталось участников |
| ← Error 400 | `detail` | string | Нельзя удалить единственного админа |
| ← Error 403 | `detail` | string | Нет прав |
| ← Error 404 | `detail` | string | Участник не найден в чате |

---

### Users

#### `GET /users/search/?q=`
Поиск пользователей по телефону или имени. Исключает текущего пользователя. Максимум 20 результатов.

| Direction | Field | Type | Description |
|-----------|-------|------|-------------|
| → Query | `q` | string | Поиск по phone / first_name / last_name (icontains) |
| ← Response | `results[].id` | UUID | |
| ← Response | `results[].phone` | string | |
| ← Response | `results[].email` | string | |
| ← Response | `results[].first_name` | string | |
| ← Response | `results[].last_name` | string | |
| ← Response | `[]` | array | Пустой массив при отсутствии результатов или пустом `q` |

---

### Общие объекты (Reference)

**User:**
```json
{ "id": "uuid", "phone": "+7999...", "email": "...", "first_name": "...", "last_name": "..." }
```

**Message:**
```json
{ "id": "uuid", "chat": "uuid", "sender": { "User" }, "text": "...", "created_at": "ISO8601", "is_read": false }
```

**ChatDetail:**
```json
{ "id": "uuid", "type": "PRIVATE|GROUP", "name": "...", "members": ["User"], "created_at": "ISO8601" }
```

**Paginated Response:**
```json
{ "count": 150, "next": "/api/v1/chats/?page=2", "previous": null, "results": [] }
```

### Dev Client
- Single-file Vue 3 SPA в `templates/messenger/chat.html`
- Auth flow (register/login/logout) с localStorage
- Auto-refresh JWT при 401
- Chat list + message history + send
- New private chat creation by phone search
- Polling every 2s for new messages

## 🚧 В планах (приоритет по убыванию)

### Phase 2: Real-time
- [ ] Django Channels + Redis layer
- [ ] WebSocket consumer для сообщений
- [ ] Замена polling на WS listener в chat.html
- [ ] Online/offline статусы

### Phase 3: Production Frontend
- [ ] Отдельный репозиторий: Vue 3 + Vite + TypeScript + Pinia
- [ ] Vue Router (auth / chats / profile)
- [ ] Компонентная архитектура
- [ ] Удаление embedded chat.html из Django

### Phase 4: Features
- [ ] Read receipts (per-message + per-chat)
- [ ] File/image upload (S3 / local storage)
- [ ] Push notifications
- [ ] Message editing / deletion
- [ ] Typing indicators

### Phase 5: Quality & Ops
- [ ] pytest + factory_boy + coverage > 80%
- [ ] Pre-commit hooks (ruff, mypy)
- [ ] CI/CD (GitHub Actions)
- [ ] Rate limiting (django-ratelimit)
- [ ] Logging + Sentry
- [ ] Nginx reverse proxy + SSL

## ⚠️ Известные ограничения / Tech Debt

1. **Polling вместо WebSocket** — приемлемо для dev, недопустимо для prod
2. **Нет rate limiting** — API открыт для abuse
3. **Нет тестов** — покрытие 0%
4. **SECRET_KEY в .env** — дефолтное значение insecure, менять перед любым деплоем
5. **Gunicorn --reload в docker-compose** — удобно для dev, убрать в prod
6. **Embedded client** — временное решение, не масштабировать
7. **is_read флаг** — есть в модели, но не используется в логике
8. **Нет soft-delete** — удаление чата/сообщения физическое

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
