from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Prefetch
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import viewsets, permissions, status, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView

from .consumers import message_payload
from .serializers import (
    AddMemberSerializer,
    PrivateChatCreateSerializer,
    RegisterSerializer,
    RegisterResponseSerializer,
    RemoveMemberSerializer,
    UserSerializer,
    MeSerializer,
)
from .models import Chat, Message, Membership
from .serializers import (
    ChatListSerializer,
    ChatDetailSerializer,
    MessageSerializer,
    MessageCreateSerializer,
)

User = get_user_model()


class IsAuthenticated(permissions.IsAuthenticated):
    pass


class ChatViewSet(viewsets.ModelViewSet):
    """
    Управление чатами и сообщениями.

    - list: Список чатов текущего пользователя с последним сообщением
    - retrieve: Детальная информация о чате со списком участников
    - create: Создание нового чата (создатель автоматически становится админом)
    - messages: История сообщений чата с пагинацией
    - send_message: Отправка текстового сообщения в чат
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        # 👈 Защита от spectular fake view
        if getattr(self, "swagger_fake_view", False):
            return Chat.objects.none()

        user = self.request.user
        return (
            Chat.objects.filter(members=user)
            .prefetch_related(
                "members",
                Prefetch(
                    "messages",
                    queryset=Message.objects.order_by("-created_at")[:1],
                    to_attr="last_msg_list",
                ),
            )
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ChatListSerializer
        elif self.action == "retrieve":
            return ChatDetailSerializer
        return ChatDetailSerializer

    def perform_create(self, serializer):
        chat = serializer.save()
        Membership.objects.create(user=self.request.user, chat=chat, is_admin=True)

    def _check_membership(self, chat, user, require_admin=False):
        """Проверка участия и прав в чате"""
        try:
            membership = Membership.objects.get(chat=chat, user=user)
            if require_admin and not membership.is_admin:
                return False, "Недостаточно прав (требуется роль администратора)"
            return True, None
        except Membership.DoesNotExist:
            return False, "Вы не являетесь участником этого чата"

    @extend_schema(
        summary="История сообщений чата",
        description="Возвращает список сообщений конкретного чата с пагинацией (по умолчанию 50 на страницу)",
        parameters=[
            OpenApiParameter(
                name="page",
                type=int,
                required=False,
                description="Номер страницы",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=MessageSerializer(many=True),
                description="Список сообщений",
            ),
            403: OpenApiResponse(
                description="Пользователь не является участником чата"
            ),
            404: OpenApiResponse(description="Чат не найден"),
        },
        tags=["Messages"],
    )
    @action(detail=True, methods=["get"])
    def messages(self, request, pk: UUID = None):
        chat = self.get_object()
        if not chat.members.filter(id=request.user.id).exists():
            return Response(
                {"detail": "Вы не участник этого чата"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Новые сообщения — на первой странице; внутри страницы порядок по возрастанию
        messages = chat.messages.select_related("sender").order_by("-created_at")

        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(
                page[::-1], many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = MessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Отправить сообщение",
        description="Отправляет текстовое сообщение в указанный чат. Chat и sender определяются автоматически.",
        request=MessageCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=MessageSerializer,
                description="Сообщение успешно создано",
            ),
            400: OpenApiResponse(description="Ошибка валидации текста"),
            403: OpenApiResponse(
                description="Пользователь не является участником чата"
            ),
            404: OpenApiResponse(description="Чат не найден"),
        },
        tags=["Messages"],
    )
    @action(detail=True, methods=["post"], url_path="send")
    def send_message(self, request, pk: UUID = None):
        chat = self.get_object()
        if not chat.members.filter(id=request.user.id).exists():
            return Response(
                {"detail": "Вы не участник этого чата"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.create(
            chat=chat,
            sender=request.user,
            text=serializer.validated_data["text"],
        )

        # Real-time доставка подключённым WS-клиентам (тот же формат, что у ChatConsumer)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat.id}",
            {"type": "chat.message", "message": message_payload(message)},
        )

        return Response(
            MessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Добавить участника в чат",
        description="Добавляет пользователя в групповой чат. Требуются права администратора.",
        request=AddMemberSerializer,
        responses={
            201: OpenApiResponse(description="Пользователь успешно добавлен"),
            400: OpenApiResponse(
                description="Ошибка валидации или пользователь уже в чате"
            ),
            403: OpenApiResponse(
                description="Нет прав администратора или вы не в чате"
            ),
            404: OpenApiResponse(description="Чат не найден"),
        },
        tags=["Members"],
    )
    @action(detail=True, methods=["post"], url_path="add-member")
    def add_member(self, request, pk: UUID = None):
        chat = self.get_object()

        # Проверка: только админ может добавлять
        ok, error = self._check_membership(chat, request.user, require_admin=True)
        if not ok:
            return Response({"detail": error}, status=status.HTTP_403_FORBIDDEN)

        # В личный чат добавлять участников нельзя (иначе ломается поиск дубликатов)
        if chat.type == Chat.ChatType.PRIVATE:
            return Response(
                {"detail": "Нельзя добавить участника в личный чат"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_to_add = User.objects.get(id=serializer.validated_data["user_id"])

        # Проверка: не состоит ли уже в чате
        if Membership.objects.filter(chat=chat, user=user_to_add).exists():
            return Response(
                {"detail": "Пользователь уже является участником этого чата"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Membership.objects.create(chat=chat, user=user_to_add, is_admin=False)

        return Response(
            {"detail": f"Пользователь {user_to_add.phone} добавлен в чат"},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Удалить участника из чата",
        description="Удаляет пользователя из чата. Админ может удалять других, обычный участник — только себя.",
        request=RemoveMemberSerializer,
        responses={
            200: OpenApiResponse(description="Пользователь удалён из чата"),
            400: OpenApiResponse(description="Нельзя удалить создателя / ошибка"),
            403: OpenApiResponse(description="Нет прав"),
            404: OpenApiResponse(description="Чат или участник не найдены"),
        },
        tags=["Members"],
    )
    @action(detail=True, methods=["post"], url_path="remove-member")
    def remove_member(self, request, pk: UUID = None):
        chat = self.get_object()

        serializer = RemoveMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_to_remove_id = serializer.validated_data["user_id"]
        is_self_leave = str(request.user.id) == str(user_to_remove_id)

        # Если удаляет другого — нужны права админа
        if not is_self_leave:
            ok, error = self._check_membership(chat, request.user, require_admin=True)
            if not ok:
                return Response({"detail": error}, status=status.HTTP_403_FORBIDDEN)

        try:
            membership = Membership.objects.get(chat=chat, user_id=user_to_remove_id)
        except Membership.DoesNotExist:
            return Response(
                {"detail": "Пользователь не найден в этом чате"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Защита: нельзя кикнуть единственного админа
        if (
            membership.is_admin
            and Membership.objects.filter(chat=chat, is_admin=True).count() == 1
        ):
            return Response(
                {"detail": "Нельзя удалить единственного администратора чата"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.delete()

        # Если в чате не осталось участников — удаляем сам чат
        if not Membership.objects.filter(chat=chat).exists():
            chat.delete()
            return Response({"detail": "Чат удалён, так как не осталось участников"})

        return Response({"detail": "Пользователь удалён из чата"})

    @extend_schema(
        summary="Создать или получить личный чат",
        description=(
            "Создаёт приватный чат с указанным пользователем. "
            "Если личный чат между вами уже существует — возвращает существующий."
        ),
        request=PrivateChatCreateSerializer,
        responses={
            200: ChatDetailSerializer,
            201: ChatDetailSerializer,
            400: OpenApiResponse(description="Ошибка валидации"),
        },
        tags=["Chats"],
    )
    @action(detail=False, methods=["post"], url_path="private")
    def create_private(self, request):
        """
        detail=False означает, что этот endpoint вызывается без ID чата:
        POST /api/v1/chats/private/
        """
        serializer = PrivateChatCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        interlocutor_id = serializer.validated_data["interlocutor_id"]

        # Ищем существующий личный чат между этими двумя пользователями
        # Аннотируем чаты количеством участников и фильтруем PRIVATE
        existing_chat = (
            Chat.objects.filter(
                type=Chat.ChatType.PRIVATE,
                members=request.user,
            )
            .annotate(member_count=Count("members"))
            .filter(member_count=2, members__id=interlocutor_id)
            .first()
        )

        if existing_chat:
            return Response(
                ChatDetailSerializer(existing_chat, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        # Создаём новый личный чат
        chat = Chat.objects.create(type=Chat.ChatType.PRIVATE)
        Membership.objects.bulk_create(
            [
                Membership(chat=chat, user=request.user, is_admin=False),
                Membership(chat=chat, user_id=interlocutor_id, is_admin=False),
            ]
        )

        return Response(
            ChatDetailSerializer(chat, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class RegisterView(generics.CreateAPIView):
    """
    Регистрация нового пользователя.
    Возвращает JWT-токены сразу после успешной регистрации.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Генерируем токены
        refresh = RefreshToken.for_user(user)
        tokens = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }

        response_data = {
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            **tokens,
        }

        response_serializer = RegisterResponseSerializer(response_data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class UserSearchView(generics.ListAPIView):
    """Поиск пользователей по номеру телефона или имени"""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Поиск пользователей",
        parameters=[
            OpenApiParameter(
                name="q",
                type=str,
                required=True,
                description="Поиск по телефону или имени",
            ),
        ],
        tags=["Users"],
    )
    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip()
        if not query:
            return User.objects.none()

        from django.db.models import Q

        return User.objects.filter(
            Q(phone__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        ).exclude(id=self.request.user.id)[:20]  # Максимум 20 результатов


class MeView(APIView):
    """
    GET /auth/me/ — профиль текущего аутентифицированного пользователя.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Текущий пользователь",
        description="Возвращает профиль аутентифицированного пользователя по JWT-токену.",
        responses={200: MeSerializer},
        tags=["auth"],
    )
    def get(self, request):
        serializer = MeSerializer(request.user)
        return Response(serializer.data)
