"""
YORVYN — Aspect-Ratio-Preserving Garment Image Preprocessing Pipeline.
Ensures zero-distortion letterboxing, exact coordinate inversion, and numerical
parity between Python (PyTorch) and browser (WebGL2/WebGPU ONNX Runtime) execution.
"""

from typing import Tuple, Dict, Any, Optional, List
import numpy as np
from PIL import Image
import torch
import torchvision.transforms as T
import io
import base64


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
NEUTRAL_GRAY = (128, 128, 128)


def letterbox_image(
    image: Image.Image,
    target_size: Tuple[int, int] = (224, 224),
    fill_color: Tuple[int, int, int] = NEUTRAL_GRAY
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Resizes image with aspect ratio preservation and neutral padding.
    Guarantees no non-isotropic stretching of garments.
    """
    img_rgb = image.convert("RGB")
    orig_w, orig_h = img_rgb.size
    target_w, target_h = target_size

    scale = min(target_w / max(orig_w, 1), target_h / max(orig_h, 1))
    new_w = max(1, int(round(orig_w * scale)))
    new_h = max(1, int(round(orig_h * scale)))

    resized_img = img_rgb.resize((new_w, new_h), Image.Resampling.BILINEAR)

    letterboxed = Image.new("RGB", (target_w, target_h), fill_color)
    pad_left = (target_w - new_w) // 2
    pad_top = (target_h - new_h) // 2
    pad_right = target_w - new_w - pad_left
    pad_bottom = target_h - new_h - pad_top

    letterboxed.paste(resized_img, (pad_left, pad_top))

    metadata = {
        "orig_w": orig_w,
        "orig_h": orig_h,
        "target_w": target_w,
        "target_h": target_h,
        "new_w": new_w,
        "new_h": new_h,
        "scale": scale,
        "pad_left": pad_left,
        "pad_top": pad_top,
        "pad_right": pad_right,
        "pad_bottom": pad_bottom,
        "fill_color": list(fill_color)
    }

    return letterboxed, metadata


def preprocess_for_model(
    image: Image.Image,
    target_size: Tuple[int, int] = (224, 224),
    fill_color: Tuple[int, int, int] = NEUTRAL_GRAY
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """
    Processes image into a normalized CHW PyTorch tensor ready for neural inference.
    Matches ONNX Runtime browser preprocessing exactly.
    """
    letterboxed, meta = letterbox_image(image, target_size=target_size, fill_color=fill_color)

    # Convert to float tensor [0.0, 1.0]
    np_img = np.array(letterboxed, dtype=np.float32) / 255.0  # HWC
    # Normalize with ImageNet mean and std
    np_img = (np_img - np.array(IMAGENET_MEAN, dtype=np.float32)) / np.array(IMAGENET_STD, dtype=np.float32)
    # Permute to CHW and add batch dimension
    tensor = torch.from_numpy(np_img).permute(2, 0, 1).unsqueeze(0).float()

    return tensor, meta


def crop_garment_instance(
    image: Image.Image,
    bbox: Tuple[int, int, int, int],
    mask: Optional[np.ndarray] = None,
    pad_factor: float = 0.06,
    target_size: Tuple[int, int] = (224, 224),
    suppress_background: bool = False
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Extracts an individual garment crop from a source photograph, applies padding,
    optional alpha masking to suppress background, and returns an aspect-ratio-preserved letterboxed image.
    """
    orig_w, orig_h = image.size
    min_x, min_y, max_x, max_y = bbox

    # Expand box slightly to avoid cutting off garment edges/seams
    box_w = max_x - min_x
    box_h = max_y - min_y
    pad_x = int(box_w * pad_factor)
    pad_y = int(box_h * pad_factor)

    crop_x1 = max(0, min_x - pad_x)
    crop_y1 = max(0, min_y - pad_y)
    crop_x2 = min(orig_w, max_x + pad_x)
    crop_y2 = min(orig_h, max_y + pad_y)

    cropped_pil = image.crop((crop_x1, crop_y1, crop_x2, crop_y2))

    if suppress_background and mask is not None:
        cropped_mask = mask[crop_y1:crop_y2, crop_x1:crop_x2]
        crop_np = np.array(cropped_pil)
        # Suppress non-mask pixels with neutral gray
        bg_fill = np.array(NEUTRAL_GRAY, dtype=np.uint8)
        mask_3d = np.repeat((cropped_mask > 20)[:, :, np.newaxis], 3, axis=2)
        crop_np = np.where(mask_3d, crop_np, bg_fill)
        cropped_pil = Image.fromarray(crop_np)

    letterboxed_crop, letterbox_meta = letterbox_image(
        cropped_pil,
        target_size=target_size,
        fill_color=NEUTRAL_GRAY
    )

    metadata = {
        "crop_bounds": [crop_x1, crop_y1, crop_x2, crop_y2],
        "crop_w": crop_x2 - crop_x1,
        "crop_h": crop_y2 - crop_y1,
        "letterbox": letterbox_meta
    }

    return letterboxed_crop, metadata


def map_coords_to_source(
    letterbox_x: float,
    letterbox_y: float,
    metadata: Dict[str, Any]
) -> Tuple[float, float]:
    """Inverts letterbox coordinates back to original source photograph coordinates."""
    pad_left = metadata.get("pad_left", 0)
    pad_top = metadata.get("pad_top", 0)
    scale = metadata.get("scale", 1.0)

    unpadded_x = letterbox_x - pad_left
    unpadded_y = letterbox_y - pad_top

    orig_x = max(0.0, min(float(metadata.get("orig_w", 0)), unpadded_x / scale))
    orig_y = max(0.0, min(float(metadata.get("orig_h", 0)), unpadded_y / scale))

    return orig_x, orig_y


def pil_to_data_url(image: Image.Image, format: str = "PNG", quality: int = 90) -> str:
    """Encodes PIL image as base64 data URL."""
    buf = io.BytesIO()
    if format.upper() == "JPEG" or format.upper() == "JPG":
        image.convert("RGB").save(buf, format="JPEG", quality=quality)
        mime = "image/jpeg"
    else:
        image.save(buf, format="PNG")
        mime = "image/png"
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def data_url_to_pil(data_url: str) -> Image.Image:
    """Decodes base64 data URL to PIL image."""
    if "," in data_url:
        _, b64 = data_url.split(",", 1)
    else:
        b64 = data_url
    raw_bytes = base64.b64decode(b64)
    return Image.open(io.BytesIO(raw_bytes)).convert("RGB")
