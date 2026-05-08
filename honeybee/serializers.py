from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
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
