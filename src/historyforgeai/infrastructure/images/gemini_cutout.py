"""Gemini (Nano Banana) image generation/editing for illustrated Shorts.

Uses the documented generateContent API with a text prompt and optional
inline reference image. The model may return an opaque image even when
asked for transparency; the asset-preparation service validates that.
"""
import base64
import os
import re
from pathlib import Path

import requests


MAX_IMAGE_BYTES = 25 * 1024 * 1024
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"


def gemini_image(prompt: str, reference: Path | None, transparent: bool,
                 model: str | None = None) -> bytes:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in .env for Gemini images")
    model = model or os.getenv("GEMINI_IMAGE_MODEL", DEFAULT_GEMINI_IMAGE_MODEL)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", model):
        raise ValueError("Invalid Gemini image model identifier")

    parts = [{"text": prompt + (
        " Output a single PNG character cutout with transparent background "
        "and no environment; if transparency is unavailable, use a clean "
        "uniform background for later removal." if transparent else
        " Output a single illustrated environment image, no text."
    )}]
    if reference is not None:
        reference = Path(reference)
        if not reference.is_file() or reference.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Reference must be an existing image smaller than 20 MB")
        import io
        from PIL import Image
        with Image.open(reference) as img:
            img.load()
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
        parts.append({"inline_data": {
            "mime_type": "image/png",
            "data": base64.b64encode(buf.getvalue()).decode("ascii"),
        }})

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no image candidate (check safety filters, model access or quota)")
    image_parts = [
        part["inlineData"] if "inlineData" in part else part["inline_data"]
        for part in candidates[0].get("content", {}).get("parts", [])
        if ("inlineData" in part or "inline_data" in part) and not part.get("thought", False)
    ]
    if not image_parts:
        raise ValueError("Gemini returned no image bytes (check safety filters, model access or quota)")
    image_data = image_parts[-1]
    mime = image_data.get("mimeType") or image_data.get("mime_type", "")
    if mime not in ("image/png", "image/jpeg", "image/webp"):
        raise ValueError(f"Unexpected Gemini image MIME type: {mime}")
    raw = base64.b64decode(image_data.get("data", ""), validate=True)
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Gemini image response is empty or too large")
    return raw
