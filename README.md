# 💬 Messenger API

> ⚠️ **Work in Progress**  
> Проект находится в активной разработке.

Real-time мессенджер с бэкендом на Django Channels и фронтендом на Vue 3.

## 🛠 Стек

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Backend | Django + DRF + Channels | 5.1+ / 3.15+ / 4.x |
| Database | PostgreSQL | 18 |
| Cache/PubSub | Redis | 7 |
| Auth | JWT (SimpleJWT) | — |
| API Docs | drf-spectacular (OpenAPI 3.0) | — |
| Frontend | Vue 3 + TypeScript + Pinia | 3.x |
| Build Tool | Vite | 6.x |
| Server | Daphne (ASGI) | — |
| Containerization | Docker Compose | — |

### Инфраструктура
- Docker Compose (backend + frontend + PostgreSQL + Redis)
- Daphne ASGI server
- Redis Pub/Sub channel layer
- Swagger UI (`/api/v1/docs/`)
- Vite dev server с proxy
- Nginx для production-раздачи frontend

## ✅ Реализованный функционал

### Аутентификация
- Регистрация с валидацией пароля
- JWT login / refresh / logout
- Авто-refresh токена при 401
- Восстановление сессии при перезагрузке страницы

### Чаты
- Создание личных чатов (идемпотентно, без дубликатов)
- Создание групповых чатов
- Список чатов с последним сообщением
- Управление участниками (добавление/удаление/выход)
- Поиск пользователей по телефону/имени

### Сообщения
- Отправка текстовых сообщений
- История сообщений с пагинацией
- **Real-time доставка через WebSocket**
- **Read receipts** (✓ отправлено / ✓✓ прочитано)
- REST fallback при недоступности WebSocket

### Real-time (WebSocket)
- Мгновенная доставка сообщений
- Онлайн/оффлайн статусы участников
- Авто-reconnect при разрыве соединения
- JWT-аутентификация через query string

### Frontend (Vue 3 SPA)
- Авторизация с защищёнными роутами
- Debounced поиск пользователей для создания чата
- Индикатор статуса WebSocket-соединения
- Адаптивный layout (sidebar + chat area)

## 🚀 Быстрый старт

### Prerequisites
- Docker & Docker Compose
- Node.js 20+

```bash
# Клонировать и запустить
git clone <repo-url> && cd messenger
cp .env.example .env  # Создай .env из примера
docker compose up --build -d

# Создать суперпользователя
docker compose exec web python manage.py createsuperuser
```

Vue 3 SPA (dev)
http://localhost:8000/api/v1/

Swagger UI
http://localhost:8000/api/v1/docs/

Django Admin
http://localhost:8000/admin/

## 📋 Планы развития
- [x] Визуальный онлайн-статус собеседника
- [ ] Групповые чаты из UI (создание + управление участниками)
- [ ] Пагинация сообщений (infinite scroll)
- [ ] Typing indicators
- [ ] Загрузка файлов и изображений
- [ ] Message editing / deletion
- [ ] Тесты (pytest + Vitest)
- [ ] CI/CD pipeline
- [ ] Rate limiting
- [ ] Production deploy (nginx + SSL)