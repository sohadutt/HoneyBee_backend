from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener


register_heif_opener()


@dataclass(frozen=True)
class ProcessedProfileImage:
    highres: bytes
    blurred: bytes
    extension: str
    content_type: str


def process_profile_image(uploaded_file: UploadedFile) -> ProcessedProfileImage:
    try:
        image = Image.open(uploaded_file)
    except UnidentifiedImageError as exc:
        raise ValueError("Upload a valid image file.") from exc

    image = ImageOps.exif_transpose(image).convert("RGB")

    highres_image = image.copy()
    highres_image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)

    blurred_image = image.copy()
    blurred_image.thumbnail((600, 600), Image.Resampling.LANCZOS)
    blurred_image = blurred_image.filter(ImageFilter.GaussianBlur(radius=18))

    return ProcessedProfileImage(
        highres=_encode_webp(highres_image, quality=82),
        blurred=_encode_webp(blurred_image, quality=45),
        extension="webp",
        content_type="image/webp",
    )


def _encode_webp(image: Image.Image, quality: int) -> bytes:
    output = BytesIO()
    image.save(output, format="WEBP", quality=quality, method=6)
    return output.getvalue()
