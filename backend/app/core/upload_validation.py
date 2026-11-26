"""
Shared streaming upload validator for YORVYN image endpoints.

Enforces chunked size limits, strict magic-byte verification (JPEG/PNG/WebP),
and Pillow decompression-bomb pixel limits.
"""

from __future__ import annotations

import io
from fastapi import HTTPException, UploadFile, status
from PIL import Image

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_IMAGE_PIXELS = 50_000_000  # 50 MP decompression-bomb defense
_CHUNK_SIZE = 64 * 1024

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _has_valid_image_magic_bytes(data: bytes) -> bool:
    if data.startswith(b"\xff\xd8\xff"):
        return True  # JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True  # PNG
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True  # WebP
    return False


async def read_and_validate_image_upload(
    upload: UploadFile,
    *,
    field_name: str = "image",
    max_bytes: int = MAX_UPLOAD_BYTES,
    min_bytes: int = 32,
) -> bytes:
    """Stream an UploadFile in chunks, validate magic bytes and decoded image dimensions."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{field_name} exceeds maximum allowed size of {max_bytes // (1024 * 1024)}MB.",
            )
        chunks.append(chunk)

    data = b"".join(chunks)
    if len(data) < min_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} is empty or too small to be a valid image.",
        )

    if not _has_valid_image_magic_bytes(data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a valid JPEG, PNG, or WebP image (invalid magic bytes).",
        )

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            if width <= 0 or height <= 0 or (width * height) > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field_name} dimensions exceed allowed pixel limit.",
                )
    except HTTPException:
        raise
    except Image.DecompressionBombError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} rejected as potential decompression bomb.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} could not be decoded as a valid image.",
        ) from exc

    return data
