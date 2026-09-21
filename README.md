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
- Авто-refresh токена при 401 (на клиенте и в Swagger)

### Чаты
- Создание групповых чатов
- Создание / поиск личных чатов по ID собеседника (без дубликатов)
- Список чатов пользователя с последним сообщением
- Детальная информация о чате с участниками

### Сообщения
- Отправка текстовых сообщений
- История сообщений с пагинацией
- Поллинг новых сообщений каждые 2 сек (dev-костыль)

### Управление участниками
- Добавление участников в групповой чат (только админ)
- Удаление участников / выход из чата
- Защита от удаления единственного админа
- Автоматическое удаление пустого чата

### Инфраструктура
- Docker Compose (web + postgres)
- Swagger UI по адресу `/api/v1/docs/`
- Встроенный dev-клиент по адресу `/api/v1/`
- Поиск пользователей по телефону / имени

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

#### 📋 Планы развития

- WebSocket (Django Channels) для real-time сообщений
- Вынос фронтенда в отдельный репозиторий (Vue 3 + Vite + Pinia)
- Статусы сообщений (delivered, read)
- Загрузка файлов и изображений
- Уведомления (push / email)
- Rate limiting
- Тесты (pytest + factory_boy)
- CI/CD pipeline