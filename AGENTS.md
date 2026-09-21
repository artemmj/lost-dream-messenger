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

### API Endpoints
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
| POST | `/chats/{id}/send/` | Отправить сообщение |
| POST | `/chats/{id}/add-member/` | Добавить участника (admin only) |
| POST | `/chats/{id}/remove-member/` | Удалить / выйти |
| GET | `/users/search/?q=` | Поиск по телефону/имени |
| GET | `/docs/` | Swagger UI |
| GET | `/schema/` | OpenAPI 3.0 schema |

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
