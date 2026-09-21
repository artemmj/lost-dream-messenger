from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Chat, Membership, Message


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]  # Удобно при большом кол-ве юзеров


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "name", "created_at", "members_count")
    list_filter = ("type", "created_at")
    search_fields = ("name", "members__username")
    inlines = [MembershipInline]

    def members_count(self, obj):
        return obj.members.count()

    members_count.short_description = "Участников"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "chat", "sender", "short_text", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("text", "sender__username")
    readonly_fields = ("chat", "sender", "created_at")

    def short_text(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
