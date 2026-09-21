from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
import uuid


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=12, unique=True)

    # avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    bio = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.username

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class Chat(models.Model):
    class ChatType(models.TextChoices):
        PRIVATE = "PRIVATE", "Личный"
        GROUP = "GROUP", "Групповой"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(
        max_length=10, choices=ChatType.choices, default=ChatType.PRIVATE
    )
    name = models.CharField(
        max_length=255, blank=True, help_text="Название для групповых чатов"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Membership", related_name="chats"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} chat {self.id}"


class Membership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "chat")
        constraints = [
            # Уникальность участника в чате (на уровне БД)
            models.UniqueConstraint(fields=["user", "chat"], name="unique_user_chat")
        ]

    def __str__(self):
        return f"{self.user.username} in {self.chat.id}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    text = models.TextField(max_length=5000)  # Ограничение на текст
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(
        default=False, db_index=True
    )  # Пока просто флаг, без усложнений

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["chat", "created_at"]
            ),  # Для быстрой пагинации сообщений в чате
        ]

    def __str__(self):
        return f"Message from {self.sender.username} at {self.created_at}"
