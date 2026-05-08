from __future__ import annotations

import re

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import serializers

from .models import Conversation, Kink, Match, Message, MessagingWebhookEvent, User
from .services import Recommendation


class KinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kink
        fields = ["id", "name", "description"]


class UserSerializer(serializers.ModelSerializer):
    kinks = KinkSerializer(many=True, read_only=True)
    kink_ids = serializers.PrimaryKeyRelatedField(
        queryset=Kink.objects.all(),
        many=True,
        write_only=True,
        required=False,
        source="kinks",
    )
    age = serializers.IntegerField(read_only=True)
    blurred_pictures_urls = serializers.ListField(
        child=serializers.URLField(),
        read_only=True,
        source="lowres_pictures_urls",
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "phone",
            "country",
            "date_of_birth",
            "age",
            "bio",
            "match_radius_km",
            "match_dominance_preferences",
            "tier",
            "first_name",
            "last_name",
            "is_verified",
            "sex",
            "orientation",
            "blurred_pictures_urls",
            "lowres_pictures_urls",
            "highres_pictures_urls",
            "dominance",
            "kinks",
            "kink_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tier", "is_verified", "created_at", "updated_at"]


class UserCreateSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])

    class Meta(UserSerializer.Meta):
        fields = [*UserSerializer.Meta.fields, "password"]

    @transaction.atomic
    def create(self, validated_data: dict[str, object]) -> User:
        kinks = validated_data.pop("kinks", [])
        password = str(validated_data.pop("password"))
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user.kinks.set(kinks)
        return user


class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, User]:
        email = str(attrs["email"]).strip().lower()
        password = str(attrs["password"])
        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )
        if user is None:
            raise serializers.ValidationError("Unable to log in with provided credentials.")
        if not isinstance(user, User):
            raise serializers.ValidationError("Unable to log in with provided credentials.")
        if not user.is_verified:
            raise serializers.ValidationError("Verify your account before logging in.")
        return {"user": user}


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.RegexField(regex=r"^\d{6}$")


class GoogleLoginSerializer(serializers.Serializer):
    credential = serializers.CharField(required=False, trim_whitespace=False)
    token = serializers.CharField(required=False, trim_whitespace=False)
    username = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    country = serializers.ChoiceField(choices=User.CountryCode.choices, required=False)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    sex = serializers.ChoiceField(choices=User.Sex.choices, required=False)
    orientation = serializers.ChoiceField(choices=User.Orientation.choices, required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        token = str(attrs.get("credential") or attrs.get("token") or "")
        if not token:
            raise serializers.ValidationError("Google credential is required.")

        client_id = settings.GOOGLE_OAUTH_CLIENT_ID
        if not client_id:
            raise serializers.ValidationError("Google login is not configured.")

        try:
            payload = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        except ValueError as exc:
            raise serializers.ValidationError("Invalid Google credential.") from exc

        if not payload.get("email_verified"):
            raise serializers.ValidationError("Google account email is not verified.")

        email = str(payload.get("email") or "").strip().lower()
        if not email:
            raise serializers.ValidationError("Google credential did not include an email.")

        username = str(attrs.get("username") or "").strip()
        if username and User.objects.filter(username=username).exclude(email=email).exists():
            raise serializers.ValidationError({"username": "This username is already in use."})

        attrs["google_payload"] = payload
        attrs["email"] = email
        return attrs

    @transaction.atomic
    def save(self, **kwargs: object) -> User:
        email = str(self.validated_data["email"])
        payload = self.validated_data["google_payload"]
        if not isinstance(payload, dict):
            raise serializers.ValidationError("Invalid Google credential.")

        user = User.objects.filter(email=email).first()
        if user is not None:
            if not user.is_verified:
                user.is_verified = True
                user.save(update_fields=["is_verified", "updated_at"])
            return user

        missing_fields = [
            field
            for field in ["phone", "country", "sex", "orientation"]
            if not self.validated_data.get(field)
        ]
        if missing_fields:
            raise serializers.ValidationError(
                {"missing_fields": missing_fields, "detail": "Complete these fields to create a HoneyBee account."}
            )

        username = str(self.validated_data.get("username") or "").strip() or _generate_username_from_email(email)
        first_name = str(self.validated_data.get("first_name") or payload.get("given_name") or "")
        last_name = str(self.validated_data.get("last_name") or payload.get("family_name") or "")
        user = User(
            username=username,
            email=email,
            phone=str(self.validated_data["phone"]),
            country=str(self.validated_data["country"]),
            first_name=first_name,
            last_name=last_name,
            sex=str(self.validated_data["sex"]),
            orientation=str(self.validated_data["orientation"]),
            is_verified=True,
        )
        user.set_unusable_password()
        user.save()
        return user


def _generate_username_from_email(email: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9@.+_-]", "", email.split("@")[0])[:140].lower() or "user"
    username = base[:150]
    suffix = 1
    while User.objects.filter(username=username).exists():
        username = f"{base[: 150 - len(str(suffix))]}{suffix}"
        suffix += 1
    return username


class PublicUserSerializer(serializers.ModelSerializer):
    kinks = KinkSerializer(many=True, read_only=True)
    age = serializers.IntegerField(read_only=True)
    blurred_pictures_urls = serializers.ListField(
        child=serializers.URLField(),
        read_only=True,
        source="lowres_pictures_urls",
    )

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "age",
            "bio",
            "country",
            "sex",
            "orientation",
            "dominance",
            "blurred_pictures_urls",
            "kinks",
        ]


class RecommendationSerializer(serializers.Serializer):
    user = PublicUserSerializer()
    score = serializers.IntegerField()
    shared_kinks = serializers.ListField(child=serializers.CharField())
    dominance_score = serializers.IntegerField()
    orientation_score = serializers.IntegerField()


class MatchSerializer(serializers.ModelSerializer):
    matched_user = PublicUserSerializer(read_only=True)
    common_kinks = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = Match
        fields = ["id", "matched_user", "score", "kinks_in_common_count", "common_kinks", "matched_at"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "recipient",
            "direction",
            "body",
            "provider_message_id",
            "delivered_at",
            "read_at",
            "created_at",
        ]
        read_only_fields = ["id", "direction", "provider_message_id", "delivered_at", "read_at", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    participants = PublicUserSerializer(many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "public_id", "participants", "provider_thread_id", "messages", "created_at", "updated_at"]
        read_only_fields = ["id", "public_id", "provider_thread_id", "created_at", "updated_at"]


class OutboundMessageSerializer(serializers.Serializer):
    recipient_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), source="recipient")
    body = serializers.CharField(max_length=4000, trim_whitespace=True)


class MessagingWebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessagingWebhookEvent
        fields = ["event_id", "event_type", "provider", "payload", "processed_at", "created_at"]
        read_only_fields = ["processed_at", "created_at"]
