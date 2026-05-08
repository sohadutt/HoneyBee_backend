from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import cast

import vercel_blob
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .image_processing import ProcessedProfileImage, process_profile_image
from .models import Conversation, Kink, Match, Message, MessagingWebhookEvent, User
from .serializers import (
    ConversationSerializer,
    KinkSerializer,
    MatchSerializer,
    MessagingWebhookEventSerializer,
    OutboundMessageSerializer,
    RecommendationSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .services import Recommendation, recommend_users

MAX_PROFILE_PICTURES = 6


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request: Request) -> Response:
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response(status=status.HTTP_204_NO_CONTENT)

    try:
        token = RefreshToken(str(refresh_token))
        token.blacklist()
    except AttributeError:
        return Response(status=status.HTTP_204_NO_CONTENT)
    except TokenError:
        return Response({"detail": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)

    return Response(status=status.HTTP_204_NO_CONTENT)


class KinkViewSet(viewsets.ModelViewSet):
    queryset = Kink.objects.all()
    serializer_class = KinkSerializer
    permission_classes = [IsAuthenticated]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.prefetch_related("kinks")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> type[UserSerializer] | type[UserCreateSerializer]:
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self) -> list[object]:
        if self.action == "create":
            return [AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=["get", "patch"], permission_classes=[IsAuthenticated])
    def me(self, request: Request) -> Response:
        user = cast(User, request.user)
        if request.method == "GET":
            return Response(UserSerializer(user).data)

        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get", "post", "put", "delete"],
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser],
        url_path="me/pictures",
    )
    @transaction.atomic
    def pictures(self, request: Request) -> Response:
        user = cast(User, request.user)

        if request.method == "GET":
            return Response(_profile_picture_payload(user))

        if request.method == "DELETE":
            return _delete_profile_picture(user, request)

        uploaded_files = _uploaded_picture_files(request)
        if not uploaded_files:
            return Response({"detail": "Upload at least one picture."}, status=status.HTTP_400_BAD_REQUEST)

        replaces_existing = request.method == "PUT"
        current_count = 0 if replaces_existing else len(user.highres_pictures_urls)
        if current_count + len(uploaded_files) > MAX_PROFILE_PICTURES:
            return Response(
                {"detail": f"Profiles can have at most {MAX_PROFILE_PICTURES} pictures."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            processed_images = [_process_uploaded_picture(uploaded_file) for uploaded_file in uploaded_files]
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_urls = [_save_profile_picture(user, image) for image in processed_images]
        blurred_urls = [item["blurred"] for item in uploaded_urls]
        highres_urls = [item["highres"] for item in uploaded_urls]

        user.lowres_pictures_urls = blurred_urls if replaces_existing else [*user.lowres_pictures_urls, *blurred_urls]
        user.highres_pictures_urls = highres_urls if replaces_existing else [*user.highres_pictures_urls, *highres_urls]
        user.save(update_fields=["lowres_pictures_urls", "highres_pictures_urls", "updated_at"])

        return Response(_profile_picture_payload(user), status=status.HTTP_201_CREATED)


class MatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Match]:
        return (
            Match.objects.filter(owner=self.request.user)
            .select_related("matched_user")
            .prefetch_related("matched_user__kinks", "kinks_in_common")
        )


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Conversation]:
        return (
            Conversation.objects.filter(participants=self.request.user)
            .prefetch_related("participants__kinks", "messages")
            .distinct()
        )

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    @transaction.atomic
    def send(self, request: Request) -> Response:
        serializer = OutboundMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sender = cast(User, request.user)
        recipient = cast(User, serializer.validated_data["recipient"])
        conversation = _get_or_create_conversation(sender, recipient)
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            recipient=recipient,
            direction=Message.Direction.OUTBOUND,
            body=serializer.validated_data["body"],
        )
        conversation.save(update_fields=["updated_at"])
        return Response(ConversationSerializer(conversation).data | {"message_id": message.id}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recommendations(request: Request) -> Response:
    user = cast(User, request.user)
    limit = min(int(request.query_params.get("limit", 20)), 50)
    items = recommend_users(user=user, limit=limit)

    if request.query_params.get("save_matches") == "true":
        _save_recommendations_as_matches(user, items)

    return Response(RecommendationSerializer(items, many=True).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def messaging_webhook(request: Request) -> Response:
    if not _valid_webhook_signature(request):
        return Response({"detail": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

    payload = cast(dict[str, object], request.data)
    event_id = str(payload.get("event_id") or payload.get("id") or "")
    event_type = str(payload.get("event_type") or payload.get("type") or "message.received")
    provider = str(payload.get("provider") or "generic")

    if not event_id:
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        event_id = f"{provider}:{payload_hash}"

    event, created = MessagingWebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={"event_type": event_type, "provider": provider, "payload": payload},
    )
    if not created:
        return Response({"detail": "Event already processed."}, status=status.HTTP_200_OK)

    _process_message_event(event)
    return Response(MessagingWebhookEventSerializer(event).data, status=status.HTTP_202_ACCEPTED)


def _get_or_create_conversation(user: User, recipient: User) -> Conversation:
    conversation = Conversation.objects.filter(participants=user).filter(participants=recipient).first()
    if conversation is not None:
        return conversation

    conversation = Conversation.objects.create()
    conversation.participants.set([user, recipient])
    return conversation


def _save_recommendations_as_matches(user: User, items: list[Recommendation]) -> None:
    for item in items:
        match, _created = Match.objects.update_or_create(
            owner=user,
            matched_user=item.user,
            defaults={"score": item.score, "kinks_in_common_count": len(item.shared_kinks)},
        )
        match.kinks_in_common.set(Kink.objects.filter(name__in=item.shared_kinks))


def _valid_webhook_signature(request: Request) -> bool:
    secret = getattr(settings, "MESSAGING_WEBHOOK_SECRET", "")
    if not secret:
        return True

    signature = request.headers.get("X-Honeybee-Signature", "")
    digest = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(signature, expected)


def _process_message_event(event: MessagingWebhookEvent) -> None:
    payload = cast(dict[str, object], event.payload)
    if event.event_type not in {"message.received", "message.created", "message.inbound"}:
        event.processed_at = timezone.now()
        event.save(update_fields=["processed_at"])
        return

    sender_external_id = str(payload.get("sender_external_id") or payload.get("from") or "")
    recipient_external_id = str(payload.get("recipient_external_id") or payload.get("to") or "")
    body = str(payload.get("body") or payload.get("text") or "")
    if not sender_external_id or not recipient_external_id or not body:
        event.processed_at = timezone.now()
        event.save(update_fields=["processed_at"])
        return

    sender = User.objects.filter(messaging_external_id=sender_external_id).first()
    recipient = User.objects.filter(messaging_external_id=recipient_external_id).first()
    if recipient is None:
        event.processed_at = timezone.now()
        event.save(update_fields=["processed_at"])
        return

    conversation = _get_or_create_conversation(recipient, sender) if sender else Conversation.objects.create()
    if sender is None:
        conversation.participants.add(recipient)

    Message.objects.create(
        conversation=conversation,
        sender=sender,
        recipient=recipient,
        direction=Message.Direction.INBOUND,
        body=body,
        provider_message_id=str(payload.get("message_id") or payload.get("provider_message_id") or event.event_id),
    )
    conversation.save(update_fields=["updated_at"])
    event.processed_at = timezone.now()
    event.save(update_fields=["processed_at"])


def _uploaded_picture_files(request: Request) -> list[UploadedFile]:
    files = [*request.FILES.getlist("pictures")]
    single_file = request.FILES.get("picture")
    if single_file is not None:
        files.append(single_file)
    return files


def _process_uploaded_picture(uploaded_file: UploadedFile) -> ProcessedProfileImage:
    content_type = str(getattr(uploaded_file, "content_type", ""))
    if not content_type.startswith("image/"):
        raise ValueError("Only image uploads are supported.")
    return process_profile_image(uploaded_file)


def _save_profile_picture(user: User, image: ProcessedProfileImage) -> dict[str, str]:
    picture_id = uuid.uuid4().hex
    base_path = f"profile-pictures/{user.pk}/{picture_id}"
    highres_url = _upload_blob(f"{base_path}-highres.{image.extension}", image.highres, image.content_type)
    blurred_url = _upload_blob(f"{base_path}-blurred.{image.extension}", image.blurred, image.content_type)
    return {"blurred": blurred_url, "highres": highres_url}


def _upload_blob(pathname: str, body: bytes, content_type: str) -> str:
    try:
        response = vercel_blob.put(pathname, body, {"access": "public", "contentType": content_type})
    except TypeError:
        response = vercel_blob.put(pathname, body, access="public", content_type=content_type)
    return _blob_response_url(response)


def _blob_response_url(response: object) -> str:
    if isinstance(response, dict):
        url = response.get("url") or response.get("downloadUrl")
        if isinstance(url, str):
            return url

    url = getattr(response, "url", None)
    if isinstance(url, str):
        return url

    raise ValueError("Blob upload did not return a public URL.")


def _profile_picture_payload(user: User) -> dict[str, list[str]]:
    return {
        "blurred_pictures_urls": user.lowres_pictures_urls,
        "highres_pictures_urls": user.highres_pictures_urls,
    }


def _delete_profile_picture(user: User, request: Request) -> Response:
    raw_index = request.data.get("index")
    highres_url = str(request.data.get("highres_url") or "")
    blurred_url = str(request.data.get("blurred_url") or "")

    index = _profile_picture_index(user, raw_index, highres_url, blurred_url)
    if index is None:
        return Response({"detail": "Picture not found."}, status=status.HTTP_404_NOT_FOUND)

    user.lowres_pictures_urls = [
        url for position, url in enumerate(user.lowres_pictures_urls) if position != index
    ]
    user.highres_pictures_urls = [
        url for position, url in enumerate(user.highres_pictures_urls) if position != index
    ]
    user.save(update_fields=["lowres_pictures_urls", "highres_pictures_urls", "updated_at"])
    return Response(_profile_picture_payload(user))


def _profile_picture_index(
    user: User,
    raw_index: object,
    highres_url: str,
    blurred_url: str,
) -> int | None:
    if raw_index not in {None, ""}:
        try:
            index = int(str(raw_index))
        except ValueError:
            return None
        if 0 <= index < len(user.highres_pictures_urls):
            return index
        return None

    if highres_url and highres_url in user.highres_pictures_urls:
        return user.highres_pictures_urls.index(highres_url)
    if blurred_url and blurred_url in user.lowres_pictures_urls:
        return user.lowres_pictures_urls.index(blurred_url)
    return None


@api_view(["POST"])
@permission_classes([AllowAny])
def create_user(request: Request) -> Response:
    serializer = UserCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_profile(request: Request) -> Response:
    user = cast(User, request.user)
    return Response(UserSerializer(user).data)
