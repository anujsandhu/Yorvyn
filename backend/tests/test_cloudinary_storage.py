"""
Automated Unit Tests for Cloudinary Image Storage Adapter.
Validates:
1. Uploading generated garment preview/texture bytes
2. Structured public ID path convention (yorvyn/users/{uid}/garments/{asset_id})
3. Asset deletion and cleanup
4. Optimized CDN delivery URL generation with transformations
"""

import io
from PIL import Image

from backend.app.services.storage.cloudinary_storage import CloudinaryStorageService


def _generate_test_image_bytes() -> bytes:
    """Generates synthetic 256x256 test image bytes in PNG format."""
    img = Image.new("RGBA", (256, 256), color=(60, 120, 240, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_cloudinary_upload_garment_image():
    service = CloudinaryStorageService()
    test_bytes = _generate_test_image_bytes()
    user_id = "test-user-12345678"
    asset_id = "garment_jacket_001"

    result = service.upload_garment_image(
        image_bytes=test_bytes,
        user_id=user_id,
        asset_id=asset_id,
        tags=["unit_test", "jacket"]
    )

    assert result["status"] == "uploaded"
    assert "public_id" in result
    # Check structure: yorvyn/users/{sanitized_uid}/garments/{asset_id}
    assert "yorvyn/users/" in result["public_id"]
    assert f"garments/{asset_id}" in result["public_id"]
    assert "delivery_url" in result
    assert result["delivery_url"].startswith("http")
    assert result["byte_size"] == len(test_bytes)


def test_cloudinary_get_delivery_url():
    service = CloudinaryStorageService()
    public_id = "yorvyn/users/usr123/garments/item_456"
    url = service.get_delivery_url(public_id, transformation="f_auto,q_auto,w_500")

    assert "yorvyn/users/usr123/garments/item_456" in url
    assert "cloudinary.com" in url


def test_cloudinary_delete_garment_image():
    service = CloudinaryStorageService()
    public_id = "yorvyn/users/usr123/garments/item_to_delete"
    result = service.delete_garment_image(public_id)

    assert result["status"] == "deleted"
