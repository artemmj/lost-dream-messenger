from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from django.contrib.auth import get_user_model
# from django.contrib.auth.password_validation import validate_password

from .models import Chat, Message

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=True)
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField(
        write_only=True,
        # min_length=8,
        # style={'input_type': 'password'},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        # style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "phone",
        )
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def validate_email(self, value: str) -> str:
        """Нормализация и проверка уникальности email"""
        normalized = value.lower().strip()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError(
                "Пользователь с таким email уже существует."
            )
        return normalized

    def validate_username(self, value: str) -> str:
        if value:
            if User.objects.filter(username__iexact=value).exists():
                raise serializers.ValidationError(
                    "Пользователь с таким именем уже существует."
                )
            return value.strip()
        return

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Пароли не совпадают."}
            )
        # Проверяем через встроенный в Django password validator
        # validate_password(attrs['password'])
        return attrs

    def create(self, validated_data: dict) -> User:
        username = validated_data.get("username", validated_data["phone"])
        user = User.objects.create_user(
            phone=validated_data["phone"],
            password=validated_data["password"],
            username=username,
            email=validated_data.get("email", ""),
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        return user


class RegisterResponseSerializer(serializers.Serializer):
    """Формат ответа при успешной регистрации"""

    user = serializers.DictField()
    access = serializers.CharField()
    refresh = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone", "email", "first_name", "last_name")
        read_only_fields = ("id",)


class MessageSerializer(serializers.ModelSerializer):
    """Сериалайзер для чтения сообщений (история чата)"""

    sender = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ("id", "chat", "sender", "text", "created_at", "is_read")
        read_only_fields = ("id", "chat", "sender", "created_at")


class ChatListSerializer(serializers.ModelSerializer):
    """Сериалайзер для списка чатов (нужно показать последнее сообщение и собеседника)"""

    last_message = serializers.SerializerMethodField()
    interlocutor = serializers.SerializerMethodField()  # Для личных чатов

    class Meta:
        model = Chat
        fields = ("id", "type", "name", "created_at", "last_message", "interlocutor")

    @extend_schema_field(MessageSerializer)
    def get_last_message(self, obj):
        # Предварительная выборка (prefetch) должна быть сделана во ViewSet
        if hasattr(obj, "last_msg_list") and obj.last_msg_list:
            return MessageSerializer(obj.last_msg_list[0]).data
        return None

    @extend_schema_field(UserSerializer)
    def get_interlocutor(self, obj):
        if obj.type == Chat.ChatType.PRIVATE:
            request = self.context.get("request")
            if request and request.user.is_authenticated:
                # Ищем второго участника
                for member in obj.members.all():
                    if member != request.user:
                        return UserSerializer(member).data
        return None


class ChatDetailSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)

    class Meta:
        model = Chat
        fields = ("id", "type", "name", "members", "created_at")


class MessageCreateSerializer(serializers.Serializer):
    """
    Сериалайзер для отправки сообщения.
    Принимает только текст, chat и sender определяются автоматически.
    """

    text = serializers.CharField(
        max_length=5000,
        min_length=1,
        help_text="Текст сообщения (1–5000 символов)",
    )

    def validate_text(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Сообщение не может быть пустым.")
        return value


class AddMemberSerializer(serializers.Serializer):
    """Сериалайзер для добавления участника в чат"""

    user_id = serializers.UUIDField(
        help_text="UUID пользователя, которого нужно добавить в чат"
    )

    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("Пользователь с таким ID не найден.")
        return value


class RemoveMemberSerializer(serializers.Serializer):
    """Сериалайзер для удаления участника из чата"""

    user_id = serializers.UUIDField(
        help_text="UUID пользователя, которого нужно удалить из чата"
    )


class PrivateChatCreateSerializer(serializers.Serializer):
    """
    Сериалайзер для создания/получения личного чата.
    Если личный чат с этим пользователем уже существует — вернёт его.
    """

    interlocutor_id = serializers.UUIDField(
        help_text="UUID пользователя, с которым нужно создать личный чат"
    )

    def validate_interlocutor_id(self, value):
        request = self.context.get("request")
        if request and request.user.id == value:
            raise serializers.ValidationError(
                "Нельзя создать личный чат с самим собой."
            )
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("Пользователь с таким ID не найден.")
        return value
