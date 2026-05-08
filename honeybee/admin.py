from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Conversation, Kink, Match, Message, MessagingWebhookEvent, User


@admin.register(User)
class HoneybeeUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "HoneyBee profile",
            {
                "fields": (
                    "phone",
                    "country",
                    "date_of_birth",
                    "bio",
                    "match_radius_km",
                    "match_dominance_preferences",
                    "tier",
                    "is_verified",
                    "sex",
                    "orientation",
                    "dominance",
                    "lowres_pictures_urls",
                    "highres_pictures_urls",
                    "messaging_external_id",
                )
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions", "kinks")
    list_display = ("email", "username", "first_name", "country", "tier", "is_verified", "is_staff")
    list_filter = ("country", "tier", "is_verified", "sex", "orientation", "is_staff")
    search_fields = ("email", "username", "first_name", "last_name", "phone")


@admin.register(Kink)
class KinkAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("owner", "matched_user", "score", "kinks_in_common_count", "matched_at")
    list_filter = ("matched_at",)
    search_fields = ("owner__email", "matched_user__email")
    filter_horizontal = ("kinks_in_common",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("public_id", "provider_thread_id", "created_at", "updated_at")
    search_fields = ("public_id", "provider_thread_id", "participants__email")
    filter_horizontal = ("participants",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "sender", "recipient", "direction", "created_at")
    list_filter = ("direction", "created_at")
    search_fields = ("body", "provider_message_id", "sender__email", "recipient__email")


@admin.register(MessagingWebhookEvent)
class MessagingWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "provider", "processed_at", "created_at")
    list_filter = ("event_type", "provider", "processed_at", "created_at")
    search_fields = ("event_id",)
