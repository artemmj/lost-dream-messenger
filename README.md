# 💬 Lost Dream Messenger

> ⚠️ **Work in Progress**
> Проект находится в активной разработке.

Real-time мессенджер: бэкенд на Django (DRF + Channels), фронтенд на Vue 3 (TypeScript, Pinia). Доставка сообщений через WebSocket, JWT-аутентификация, всё поднимается одним `docker compose up`.

## 🛠 Стек

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Backend | Django + DRF + Channels | 5.2 / 3.18 / 4.3 |
| Database | PostgreSQL | 18 |
| Cache/PubSub | Redis (channels_redis pub/sub) | 7 |
| Auth | JWT (SimpleJWT) | 5.5 |
| API Docs | drf-spectacular (OpenAPI 3.0) | — |
| Frontend | Vue 3 + TypeScript + Pinia + Vue Router | 3.5 |
| Build Tool | Vite | 8.x |
| Server | Daphne (ASGI, HTTP + WebSocket) | — |
| Containerization | Docker Compose | — |

## ✅ Реализованный функционал

### Аутентификация
- Регистрация (телефон как логин) + JWT сразу в ответе
- Login / refresh (SimpleJWT), авто-refresh токена при 401 на фронте
- Восстановление сессии при перезагрузке: профиль догружается через `/auth/me/`
- Logout — клиентский (очистка токенов в localStorage)

### Чаты
- Личные чаты: создание идемпотентно (существующий чат возвращается, дубликат не создаётся)
- Групповые чаты из UI: название + участники одним запросом (`member_ids`), создатель — администратор
- Управление участниками из UI: добавление/удаление (для админов), выход из чата; удалённый участник мгновенно отключается от WS (код 4003)
- Список чатов с последним сообщением и собеседником
- Поиск пользователей по телефону/имени (с исключением себя, лимит 20)

### Сообщения
- Отправка текста (до 5000 символов) через WebSocket
- REST fallback `POST /chats/{id}/send/` — с real-time рассылкой подключённым WS-клиентам
- История: первая страница = последние 50 сообщений, далее **infinite scroll вверх** с сохранением позиции скролла
- Read receipts (✓ отправлено / ✓✓ прочитано), отметка о прочтении при подключении к чату
- Участник, удалённый из чата, теряет возможность писать (проверка при каждом WS-сообщении)

### Real-time (WebSocket)
- Мгновенная доставка сообщений всем участникам чата
- **Онлайн-статус собеседника** в личном чате: presence-реестр в Redis (учитывает несколько вкладок), снимок «кто онлайн» при подключении
- События прочтения сообщений
- Авто-reconnect при разрыве соединения (фиксированная задержка 2 c)
- JWT-аутентификация через query string (`?token=<jwt>`)

### Frontend (Vue 3 SPA)
- Login/Register экраны, защищённые роуты (navigation guard)
- Sidebar со списком чатов и превью последнего сообщения
- Окно чата: live-сообщения, presence собеседника, индикатор WS-соединения, панель участников группы
- Модалка нового чата: личный (debounced-поиск) или групповой (название + мультивыбор участников)
- Vite proxy для API/WS — разработка без CORS

## 🚀 Быстрый старт

### Prerequisites
- Docker & Docker Compose
- Node.js 22+ (только для локальной разработки фронтенда вне Docker)

```bash
# Клонировать и запустить
git clone <repo-url> && cd lost-dream-messenger
cp .env.example .env
docker compose up --build -d

# Создать суперпользователя
docker compose exec backend python manage.py createsuperuser

# Логи
docker compose logs -f
```

Frontend в compose запускается в dev-режиме (Vite HMR). Prod-вариант (nginx) собирается из того же Dockerfile (`target: prod`), но отдельного сервиса в compose для него пока нет.

### Доступные URL

| URL | Описание |
|-|-|
| http://localhost:5173 | Vue 3 SPA (Vite dev) |
| http://localhost:8000/api/v1/docs/ | Swagger UI |
| http://localhost:8000/api/v1/schema/ | OpenAPI schema |
| http://localhost:8000/admin/ | Django Admin |
| localhost:5434 | PostgreSQL (проброшен на хост) |

## 📋 Планы развития
- [ ] Онлайн-статус участников в групповых чатах (в личных уже есть)
- [ ] Перечитывание истории после WS-reconnect
- [ ] Typing indicators
- [ ] Загрузка файлов и изображений
- [ ] Message editing / deletion
- [ ] Тесты (pytest + Vitest)
- [ ] CI/CD pipeline
- [ ] Rate limiting
- [ ] Настройки из env (SECRET_KEY, DEBUG) — сейчас захардкожены
- [ ] Production deploy (nginx + SSL, prod-сервис frontend в compose)

Подробное описание архитектуры, API и ограничений — в [AGENTS.md](AGENTS.md).
