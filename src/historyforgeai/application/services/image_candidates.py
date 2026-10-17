"""Image candidates from manual files or hosted image APIs; never auto-approve."""
import base64
import os
import shutil
from pathlib import Path

import requests
from PIL import Image
from historyforgeai.application.services.storyboard import load, save

SUPPORTED = ("manual", "huggingface", "openai")


def _copy_image(source: Path, destination: Path):
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    with Image.open(source) as image:
        image.verify()
    with Image.open(source) as image:
        image.convert("RGB").save(destination, format="JPEG", quality=92)


def _hosted_image(provider: str, prompt: str, destination: Path, model: str | None):
    if provider == "huggingface":
        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("Set HF_TOKEN in .env")
        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:
            raise RuntimeError("Install hosted image dependencies: pip install -e '.[images]'") from exc
        client = InferenceClient(token=token)
        image = client.text_to_image(prompt, model=model or os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell"))
        image.convert("RGB").save(destination, format="JPEG", quality=92)
    elif provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("Set OPENAI_API_KEY in .env")
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model or os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
                  "prompt": prompt, "size": "1024x1536", "n": 1},
            timeout=240,
        )
        response.raise_for_status()
        result = response.json()["data"][0]
        if "b64_json" in result:
            destination.write_bytes(base64.b64decode(result["b64_json"]))
        elif "url" in result:
            url = result["url"]
            if not url.startswith("https://"):
                raise ValueError("Image URL must use HTTPS")
            download = requests.get(url, timeout=120)
            download.raise_for_status()
            destination.write_bytes(download.content)
        else:
            raise ValueError("Image API returned neither b64_json nor url")
        # Convert any returned PNG to standard JPEG for the renderer.
        with Image.open(destination) as image:
            image.convert("RGB").save(destination.with_suffix(".tmp.jpg"), "JPEG", quality=92)
        destination.with_suffix(".tmp.jpg").replace(destination)
    else:
        raise ValueError(f"Unsupported hosted provider: {provider}")


def create_candidate(job_dir: Path, scene_index: int, provider: str = "manual",
                     source: Path | None = None, model: str | None = None,
                     allow_paid: bool = False) -> Path:
    if provider not in SUPPORTED:
        raise ValueError(f"Unsupported image provider: {provider}")
    if provider in ("huggingface", "openai") and not allow_paid:
        raise ValueError("Hosted image calls may incur charges; pass --allow-paid")
    job_dir = Path(job_dir).resolve()
    board_path = job_dir / "storyboard.json"
    board = load(board_path)
    shot = next((s for s in board.shots if s.scene_index == scene_index), None)
    if shot is None:
        raise ValueError(f"Scene {scene_index} not found")
    destination_dir = job_dir / "assets"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"candidate_scene_{scene_index:02d}.jpg"
    temp = destination_dir / f"candidate_scene_{scene_index:02d}.partial.jpg"
    try:
        if provider == "manual":
            if source is None:
                raise ValueError("--file is required for manual images")
            _copy_image(source, temp)
        else:
            _hosted_image(provider, shot.visual_description, temp, model)
        with Image.open(temp) as image:
            image.verify()
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    shot.candidate_image = str(destination)
    shot.status = "pending_review"
    shot.source_url = None
    shot.license = None
    shot.attribution = None
    save(board_path, board)
    return destination
