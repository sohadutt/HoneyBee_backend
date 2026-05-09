from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpRequest

# Removed 'Kink' from imports
from .models import Conversation, Match, Message, MessagingWebhookEvent, User


@admin.register(User)
class HoneybeeUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "HoneyBee Profile",
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
                    "kinks",  # JSON array
                    "lowres_pictures_urls",
                    "highres_pictures_urls",
                    "messaging_external_id",
                )
            },
        ),
    )
    # Ensure custom fields are available when manually creating a new user in the admin
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "HoneyBee Core Attributes",
            {
                "fields": (
                    "email",
                    "phone",
                    "country",
                    "tier",
                    "sex",
                    "orientation",
                )
            },
        ),
    )
    
    # Removed "kinks" from filter_horizontal because it is a JSONField now
    filter_horizontal = ("groups", "user_permissions")
    list_display = ("email", "username", "first_name", "country", "tier", "is_verified", "is_staff")
    list_filter = ("country", "tier", "is_verified", "sex", "orientation", "is_staff")
    search_fields = ("email", "username", "first_name", "last_name", "phone")
    readonly_fields = ("created_at", "updated_at")


# ==========================================
# REMOVED KinkAdmin entirely as it's no longer a DB table
# ==========================================


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("owner", "matched_user", "score", "kinks_in_common_count", "matched_at")
    list_filter = ("matched_at", "score")
    search_fields = ("owner__email", "matched_user__email", "owner__username", "matched_user__username")
    
    # Removed filter_horizontal = ("kinks_in_common",) because it is a JSONField now
    
    # Performance optimizations
    list_select_related = ("owner", "matched_user")
    autocomplete_fields = ("owner", "matched_user")
    readonly_fields = ("matched_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("public_id", "provider_thread_id", "created_at", "updated_at")
    search_fields = ("public_id", "provider_thread_id", "participants__email", "participants__username")
    filter_horizontal = ("participants",)
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "sender", "recipient", "direction", "created_at")
    list_filter = ("direction", "created_at", "delivered_at", "read_at")
    search_fields = ("body", "provider_message_id", "sender__email", "recipient__email")
    
    # Performance optimizations
    list_select_related = ("conversation", "sender", "recipient")
    autocomplete_fields = ("sender", "recipient")
    readonly_fields = ("created_at", "delivered_at", "read_at", "provider_message_id")


@admin.register(MessagingWebhookEvent)
class MessagingWebhookEventAdmin(admin.ModelAdmin):
    """
    Webhook events act as an immutable audit trail. 
    This admin is strictly locked down to read-only views.
    """
    list_display = ("event_id", "event_type", "provider", "processed_at", "created_at")
    list_filter = ("event_type", "provider", "processed_at", "created_at")
    search_fields = ("event_id", "payload")
    readonly_fields = ("event_id", "event_type", "provider", "payload", "processed_at", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Prevent manual creation of webhook logs."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Prevent alteration of historical webhook logs."""
        return False