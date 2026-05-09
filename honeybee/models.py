from __future__ import annotations

import logging
import secrets
from datetime import date
from typing import Any, TypeAlias

import vercel_blob
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver

# Import choices and constants from our newly created obj.py
from .obj import PREDEFINED_KINKS, CountryCode, Dominance, Orientation, Sex, Tier

logger = logging.getLogger(__name__)

# Type Aliases for JSON fields
JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


# VALIDATORS

def validate_dominance_choices(value: Any) -> None:
    """Validates that the provided JSON value is a list of valid Dominance choices."""
    if not isinstance(value, list):
        raise ValidationError("Value must be a list.")

    valid_choices = {choice[0] for choice in Dominance.choices}
    invalid_choices = [item for item in value if item not in valid_choices]
    
    if invalid_choices:
        raise ValidationError(f"{', '.join(invalid_choices)} are not valid dominance choices.")


def validate_kink_choices(value: Any) -> None:
    """Validates that the provided JSON value is a list of keys from PREDEFINED_KINKS."""
    if not isinstance(value, list):
        raise ValidationError("Value must be a list.")
        
    invalid_choices = [item for item in value if item not in PREDEFINED_KINKS]
    if invalid_choices:
        raise ValidationError(f"{', '.join(invalid_choices)} are not valid predefined kinks.")


def validate_json_url_list(value: Any) -> None:
    """Validates that the provided JSON value is a strictly formatted list of URL strings."""
    if not isinstance(value, list):
        raise ValidationError("Value must be a list.")
    if not all(isinstance(item, str) for item in value):
        raise ValidationError("Every URL must be a string.")


# MAIN USER MODEL

class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Handles matchmaking preferences, demographics, and tiered access.
    """
    objects = UserManager()

    # Core fields
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=5, choices=CountryCode.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(blank=True)
    
    # Matchmaking & Preferences
    match_radius_km = models.PositiveIntegerField(default=50)
    match_dominance_preferences = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_dominance_choices],
    )
    tier = models.IntegerField(choices=Tier.choices, default=Tier.FREE, db_index=True)
    is_verified = models.BooleanField(default=False)
    sex = models.CharField(max_length=20, choices=Sex.choices)
    orientation = models.CharField(max_length=20, choices=Orientation.choices)
    dominance = models.JSONField(default=list, blank=True, validators=[validate_dominance_choices])
    kinks = models.JSONField(default=list, blank=True, validators=[validate_kink_choices])
    
    # Media
    lowres_pictures_urls = models.JSONField(default=list, blank=True, validators=[validate_json_url_list])
    highres_pictures_urls = models.JSONField(default=list, blank=True, validators=[validate_json_url_list])
    
    # Integrations & Timestamps
    messaging_external_id = models.CharField(max_length=150, blank=True, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "phone", "country", "sex", "orientation"]

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["tier", "is_verified"]),
            models.Index(fields=["country", "sex", "orientation"]),
        ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._initial_picture_urls = self._picture_urls

    @property
    def age(self) -> int | None:
        if self.date_of_birth is None:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def is_free_tier(self) -> bool:
        return self.tier == Tier.FREE

    @property
    def su_tier(self) -> bool:
        return self.is_superuser or not self.is_free_tier

    @property
    def _picture_urls(self) -> list[str]:
        lowres_urls = self.lowres_pictures_urls if isinstance(self.lowres_pictures_urls, list) else []
        highres_urls = self.highres_pictures_urls if isinstance(self.highres_pictures_urls, list) else []
        return [url for url in [*lowres_urls, *highres_urls] if isinstance(url, str)]

    def _delete_removed_blob_urls(self) -> None:
        if not self.pk:
            return
            
        current_urls = set(self._picture_urls)
        initial_urls = set(self._initial_picture_urls)
        
        removed_urls = list(initial_urls - current_urls)
        if removed_urls:
            delete_blob_urls(removed_urls)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            self._delete_removed_blob_urls()
            
        self.full_clean()
        super().save(*args, **kwargs)
        self._initial_picture_urls = self._picture_urls

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        urls_to_delete = self._picture_urls
        result = super().delete(*args, **kwargs)
        delete_blob_urls(urls_to_delete)
        return result

    def __str__(self) -> str:
        return f"{self.first_name or self.username} ({self.email})"


# RELATED MODELS

class Match(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches")
    matched_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matched_by")
    
    kinks_in_common = models.JSONField(default=list, blank=True, validators=[validate_kink_choices])
    kinks_in_common_count = models.PositiveIntegerField(default=0)
    score = models.PositiveSmallIntegerField(default=0, db_index=True)
    matched_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-score", "-matched_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "matched_user"], name="unique_match_pair"),
            models.CheckConstraint(condition=~Q(owner=models.F("matched_user")), name="prevent_self_match"),
        ]
        indexes = [
            models.Index(fields=["owner", "matched_user"]),
            models.Index(fields=["score", "matched_at"]),
        ]

    @property
    def common_kinks(self) -> list[str]:
        return self.kinks_in_common if isinstance(self.kinks_in_common, list) else []

    def __str__(self) -> str:
        return f"Match: {self.owner_id} <-> {self.matched_user_id} (Score: {self.score})"


class Conversation(models.Model):
    public_id = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    participants = models.ManyToManyField(User, related_name="conversations")
    provider_thread_id = models.CharField(max_length=150, blank=True, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["public_id"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return str(self.public_id)


class Message(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_messages")
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_messages")
    
    direction = models.CharField(max_length=10, choices=Direction.choices)
    body = models.TextField()
    provider_message_id = models.CharField(max_length=150, blank=True, unique=True, null=True)
    
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["provider_message_id"]),
        ]

    def __str__(self) -> str:
        preview = self.body[:40] + ("..." if len(self.body) > 40 else "")
        return f"{self.get_direction_display()}: {preview}"


class MessagingWebhookEvent(models.Model):
    event_id = models.CharField(max_length=150, unique=True, default=secrets.token_urlsafe)
    event_type = models.CharField(max_length=100)
    provider = models.CharField(max_length=50, default="generic")
    payload = models.JSONField(default=dict)
    
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_id"]),
            models.Index(fields=["event_type", "provider"]),
            models.Index(fields=["processed_at"]),
        ]

    def __str__(self) -> str:
        return f"Webhook [{self.provider}]: {self.event_type} ({self.event_id})"


# UTILITIES & SIGNALS

def delete_blob_urls(urls: list[str]) -> None:
    for url in urls:
        try:
            vercel_blob.delete(url)
        except Exception as e:
            logger.error(f"Failed to delete blob at {url}: {e}")
            continue

@receiver(post_delete, sender=User)
def auto_delete_vercel_blob_on_delete(sender: type[User], instance: User, **kwargs: Any) -> None:
    if hasattr(instance, '_picture_urls') and instance._picture_urls:
        delete_blob_urls(instance._picture_urls)