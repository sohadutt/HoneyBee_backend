from __future__ import annotations

import secrets
from datetime import date
from typing import TypeAlias

import vercel_blob
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


class Kink(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


def validate_dominance_choices(value: list[str]) -> None:
    if not isinstance(value, list):
        raise ValidationError("Value must be a list.")

    valid_choices = {choice[0] for choice in User.Dominance.choices}
    invalid_choices = [item for item in value if item not in valid_choices]
    if invalid_choices:
        raise ValidationError(f"{', '.join(invalid_choices)} are not valid dominance choices.")


def validate_json_url_list(value: list[str]) -> None:
    if not isinstance(value, list):
        raise ValidationError("Value must be a list.")
    if not all(isinstance(item, str) for item in value):
        raise ValidationError("Every URL must be a string.")


class User(AbstractUser):
    class Tier(models.IntegerChoices):
        FREE = 0, "Free"
        PRO = 1, "Pro"
        PREMIUM = 2, "Premium"

    class CountryCode(models.TextChoices):
        IN_91 = "IN", "India (+91)"
        US_1 = "US", "United States (+1)"
        UK_44 = "UK", "United Kingdom (+44)"
        CA_1 = "CA", "Canada (+1)"
        AU_61 = "AU", "Australia (+61)"
        DE_49 = "DE", "Germany (+49)"
        FR_33 = "FR", "France (+33)"
        JP_81 = "JP", "Japan (+81)"
        CN_86 = "CN", "China (+86)"
        BR_55 = "BR", "Brazil (+55)"

    class Orientation(models.TextChoices):
        STRAIGHT = "straight", "Straight"
        GAY = "gay", "Gay"
        LESBIAN = "lesbian", "Lesbian"
        BISEXUAL = "bisexual", "Bisexual"
        ASEXUAL = "asexual", "Asexual"
        PANSEXUAL = "pansexual", "Pansexual"
        QUEER = "queer", "Queer"
        OTHER = "other", "Other"

    class Sex(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        FTM = "ftm", "Female to Male"
        MTF = "mtf", "Male to Female"
        NON_BINARY = "non_binary", "Non-binary"
        OTHER = "other", "Other"

    class Dominance(models.TextChoices):
        DOMINANT = "dominant", "Dominant"
        SUBMISSIVE = "submissive", "Submissive"
        SWITCH = "switch", "Switch"
        TOP = "top", "Top"
        BOTTOM = "bottom", "Bottom"
        OTHER = "other", "Other"

    objects = UserManager()

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=5, choices=CountryCode.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(blank=True)
    match_radius_km = models.PositiveIntegerField(default=50)
    match_dominance_preferences = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_dominance_choices],
    )
    tier = models.IntegerField(choices=Tier.choices, default=Tier.FREE)
    is_verified = models.BooleanField(default=False)
    sex = models.CharField(max_length=20, choices=Sex.choices)
    orientation = models.CharField(max_length=20, choices=Orientation.choices)
    lowres_pictures_urls = models.JSONField(default=list, blank=True, validators=[validate_json_url_list])
    highres_pictures_urls = models.JSONField(default=list, blank=True, validators=[validate_json_url_list])
    dominance = models.JSONField(default=list, blank=True, validators=[validate_dominance_choices])
    kinks = models.ManyToManyField(Kink, blank=True, related_name="users")
    messaging_external_id = models.CharField(max_length=150, blank=True, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "phone", "country", "sex", "orientation"]

    class Meta:
        ordering = ["-created_at"]

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
        return self.tier == self.Tier.FREE

    @property
    def su_tier(self) -> bool:
        return self.is_superuser or not self.is_free_tier

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            self._delete_removed_blob_urls()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        urls_to_delete = self._picture_urls
        result = super().delete(*args, **kwargs)
        delete_blob_urls(urls_to_delete)
        return result

    def _delete_removed_blob_urls(self) -> None:
        old_user = User.objects.filter(pk=self.pk).first()
        if old_user is None:
            return
        delete_blob_urls(list(set(old_user._picture_urls) - set(self._picture_urls)))

    @property
    def _picture_urls(self) -> list[str]:
        lowres_urls = self.lowres_pictures_urls if isinstance(self.lowres_pictures_urls, list) else []
        highres_urls = self.highres_pictures_urls if isinstance(self.highres_pictures_urls, list) else []
        return [url for url in [*lowres_urls, *highres_urls] if isinstance(url, str)]

    def __str__(self) -> str:
        return f"{self.first_name or self.username} ({self.email})"


def delete_blob_urls(urls: list[str]) -> None:
    for url in urls:
        try:
            vercel_blob.delete(url)
        except Exception:
            continue


@receiver(post_delete, sender=User)
def auto_delete_vercel_blob_on_delete(sender: type[User], instance: User, **kwargs: object) -> None:
    delete_blob_urls(instance._picture_urls)


class Match(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches")
    matched_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matched_by")
    kinks_in_common = models.ManyToManyField(Kink, blank=True, related_name="matches")
    kinks_in_common_count = models.PositiveIntegerField(default=0)
    score = models.PositiveSmallIntegerField(default=0)
    matched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-score", "-matched_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "matched_user"], name="unique_match_pair"),
            models.CheckConstraint(condition=~Q(owner=models.F("matched_user")), name="prevent_self_match"),
        ]

    @property
    def common_kinks(self) -> list[str]:
        return list(self.kinks_in_common.values_list("name", flat=True))

    def __str__(self) -> str:
        return f"{self.owner_id} matched with {self.matched_user_id}"


class Conversation(models.Model):
    public_id = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    participants = models.ManyToManyField(User, related_name="conversations")
    provider_thread_id = models.CharField(max_length=150, blank=True, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.public_id


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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.direction}: {self.body[:40]}"


class MessagingWebhookEvent(models.Model):
    event_id = models.CharField(max_length=150, unique=True, default=secrets.token_urlsafe)
    event_type = models.CharField(max_length=100)
    provider = models.CharField(max_length=50, default="generic")
    payload = models.JSONField(default=dict)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_type}:{self.event_id}"
