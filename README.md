# 💬 Messenger API

> ⚠️ **Work in Progress**  
> Проект находится в активной разработке.

Минималистичный бэкенд мессенджера на современном стеке Django с встроенным dev-клиентом для быстрой разработки и тестирования API без настройки отдельного фронтенда.

## 🛠 Стек

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Backend | Django + DRF | 5.1+ / 3.15+ |
| Database | PostgreSQL | 16 |
| Auth | JWT (SimpleJWT) | — |
| API Docs | drf-spectacular (OpenAPI 3.0) | — |
| Dev Client | Vue 3 + Axios (CDN, single HTML) | 3.x |
| Containerization | Docker Compose | — |

## ✅ Реализованный функционал

### Аутентификация
- Регистрация с валидацией пароля и нормализацией email
- JWT login / refresh / logout
- Авто-refresh токена при 401

### Чаты
- Создание групповых и личных чатов
- Идемпотентное создание личных чатов (без дубликатов)
- Список чатов с последним сообщением
- Управление участниками (добавление/удаление/выход)

### Сообщения
- Отправка текстовых сообщений (WS + REST fallback)
- История сообщений с пагинацией
- **Real-time доставка через WebSocket**
- **Read receipts** (✓ отправлено / ✓✓ прочитано)

### Real-time (WebSocket)
- Мгновенная доставка сообщений
- Онлайн/оффлайн статусы участников
- Авто-reconnect при разрыве соединения
- JWT-аутентификация через query string

### Инфраструктура
- Docker Compose (Django + PostgreSQL + Redis)
- Daphne ASGI server
- Redis Pub/Sub channel layer
- Swagger UI (`/api/v1/docs/`)
- Встроенный dev-клиент (`/api/v1/`)

## 🚀 Быстрый старт

```bash
# Клонировать и запустить
git clone <repo-url> && cd messenger
cp .env.example .env  # Создай .env из примера
docker compose up --build -d

# Создать суперпользователя
docker compose exec web python manage.py createsuperuser
```

Dev-клиент (Vue 3)
http://localhost:8000/api/v1/

Swagger UI
http://localhost:8000/api/v1/docs/

Django Admin
http://localhost:8000/admin/

## 📋 Планы развития

- [ ] Вынос фронтенда в отдельный репозиторий (Vue 3 + Vite + Pinia)
- [ ] Загрузка файлов и изображений
- [ ] Typing indicators
- [ ] Push notifications
- [ ] Message editing / deletion
- [ ] Тесты (pytest + factory_boy)
- [ ] CI/CD pipeline
- [ ] Rate limiting