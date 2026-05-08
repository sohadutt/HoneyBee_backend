from __future__ import annotations

import base64
import smtplib
import uuid
from typing import TypedDict

import vercel_blob
from celery import Task, shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .image_processing import ProcessedProfileImage, process_profile_image_bytes
from .models import User


class ProfilePictureUpload(TypedDict):
    data: str
    content_type: str
    filename: str


class ProfilePictureUrls(TypedDict):
    blurred: str
    highres: str


class ProfilePictureTaskResult(TypedDict):
    blurred_pictures_urls: list[str]
    highres_pictures_urls: list[str]


@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self: Task, email: str, otp: str) -> str:
    try:
        send_mail(
            subject="Your HoneyBee verification code",
            message=f"Your HoneyBee verification code is {otp}. It expires in 3 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except smtplib.SMTPException as exc:
        raise self.retry(exc=exc, countdown=60) from exc

    return f"OTP sent to {email}"


@shared_task
def process_profile_pictures_task(
    user_id: int,
    uploads: list[ProfilePictureUpload],
    replaces_existing: bool,
) -> ProfilePictureTaskResult:
    user = User.objects.get(pk=user_id)
    uploaded_urls = [_process_and_save_profile_picture(user, upload) for upload in uploads]
    blurred_urls = [item["blurred"] for item in uploaded_urls]
    highres_urls = [item["highres"] for item in uploaded_urls]

    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id)
        user.lowres_pictures_urls = blurred_urls if replaces_existing else [*user.lowres_pictures_urls, *blurred_urls]
        user.highres_pictures_urls = highres_urls if replaces_existing else [*user.highres_pictures_urls, *highres_urls]
        user.save(update_fields=["lowres_pictures_urls", "highres_pictures_urls", "updated_at"])

    return {
        "blurred_pictures_urls": user.lowres_pictures_urls,
        "highres_pictures_urls": user.highres_pictures_urls,
    }


def _process_and_save_profile_picture(user: User, upload: ProfilePictureUpload) -> ProfilePictureUrls:
    image_data = base64.b64decode(upload["data"])
    image = process_profile_image_bytes(image_data)
    return _save_profile_picture(user, image)


def _save_profile_picture(user: User, image: ProcessedProfileImage) -> ProfilePictureUrls:
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
