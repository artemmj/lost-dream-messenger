from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, Chat, Membership, Message


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


class RecentMessagesInline(admin.TabularInline):
    model = Message
    verbose_name_plural = "Последние сообщения"
    fields = ("sender", "short_text_display", "created_at", "is_read")
    readonly_fields = ("sender", "short_text_display", "created_at", "is_read")
    extra = 0
    max_num = 0
    can_delete = False
    ordering = ("-created_at",)

    def get_queryset(self, request):
        """НЕ применяем срез здесь — Django добавит фильтр по chat_id позже."""
        return super().get_queryset(request).order_by("-created_at")

    def get_formset(self, request, obj=None, **kwargs):
        """Ограничиваем queryset ПОСЛЕ того как Django применил фильтр по parent."""
        formset = super().get_formset(request, obj, **kwargs)
        if obj:
            # obj — это Chat instance, к которому привязан inline
            formset.queryset = Message.objects.filter(chat=obj).order_by("-created_at")[
                :7
            ]
        return formset

    @admin.display(description="Текст")
    def short_text_display(self, obj):
        text = obj.text or ""
        return text[:80] + "..." if len(text) > 80 else text


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "name", "created_at", "members_count")
    list_filter = ("type", "created_at")
    search_fields = ("name", "members__phone")
    inlines = [MembershipInline, RecentMessagesInline]  # ← Добавили inline

    @admin.display(description="Участников")
    def members_count(self, obj):
        return obj.members.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "chat", "sender", "short_text", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("text", "sender__phone")
    readonly_fields = ("chat", "sender", "created_at")

    @admin.display(description="Текст")
    def short_text(self, obj):
        text = obj.text or ""
        return text[:50] + "..." if len(text) > 50 else text
