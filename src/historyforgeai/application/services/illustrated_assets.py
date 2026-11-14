"""Review-first illustrated asset preparation for Blender cutout scenes.

No draft is used by Blender until a human explicitly approves it.
AI image calls are opt-in and may be billed; cutout geometry is heuristic,
not automatic skeletal rigging.
"""
import base64
import hashlib
import io
import json
import os
import shutil
from pathlib import Path
from typing import Literal

import requests
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from historyforgeai.application.services.storyboard import load

STYLE = (
    "Consistent flat 2D illustrated historical documentary art, crisp silhouettes, "
    "clean vector-like shading, historically inspired Indian costumes and weapons, "
    "no words, no labels, no logos, no watermarks. "
)


class AssetDraft(BaseModel):
    scene_index: int = Field(ge=1)
    status: Literal["pending_review", "approved", "rejected"] = "pending_review"
    mode: Literal["whole", "body-arm", "puppet"]
    provider: Literal["manual", "gemini", "openai"]
    model: str | None = None
    character_id: str | None = None
    prompts: dict[str, str] = Field(default_factory=dict)
    files: dict[str, str] = Field(default_factory=dict)
    hashes: dict[str, str] = Field(default_factory=dict)
    notes: str = ""
    background_candidate: str | None = None


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _openai_image(prompt: str, reference: Path | None, transparent: bool,
                  model: str | None = None) -> bytes:
    """Generate or edit a PNG using OpenAI's documented Images API."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for hosted illustration generation")
    model = model or os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    params = {
        "model": model, "prompt": prompt, "size": "1024x1536", "n": 1,
        "background": "transparent" if transparent else "opaque",
        "output_format": "png",
    }
    headers = {"Authorization": f"Bearer {key}"}
    if reference is not None:
        with Path(reference).open("rb") as handle:
            response = requests.post(
                "https://api.openai.com/v1/images/edits", headers=headers,
                data=params,
                files={"image": (Path(reference).name, handle,
                                 "image/png" if Path(reference).suffix.lower() == ".png"
                                 else "image/webp" if Path(reference).suffix.lower() == ".webp"
                                 else "image/jpeg")},
                timeout=300,
            )
    else:
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers=headers, json=params, timeout=300,
        )
    response.raise_for_status()
    data = response.json().get("data") or []
    if not data or not data[0].get("b64_json"):
        raise ValueError("Image API returned no base64 PNG; nothing was saved")
    raw = base64.b64decode(data[0]["b64_json"], validate=True)
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError("Image API returned an oversized image")
    return raw


def _load_image_bytes(raw: bytes) -> Image.Image:
    if not raw or len(raw) > 25 * 1024 * 1024:
        raise ValueError("Image must be nonempty and under 25 MB")
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        if image.width < 16 or image.height < 16:
            raise ValueError("Image is too small")
        return image.copy()


def _transparent_png(raw: bytes, remove_background: bool) -> bytes:
    image = _load_image_bytes(raw)
    rgba = image.convert("RGBA")
    low, high = rgba.getchannel("A").getextrema()
    if low == 255:
        if not remove_background:
            raise ValueError("Image is opaque. Supply a transparent PNG or enable local background removal.")
        try:
            from rembg import remove
        except ImportError as exc:
            raise RuntimeError("Install optional background removal: pip install -e '.[cutouts]'") from exc
        rgba = _load_image_bytes(remove(raw)).convert("RGBA")
        low, high = rgba.getchannel("A").getextrema()
    if low == 255 or high == 0:
        raise ValueError("Background removal did not produce a visible transparent cutout")
    # Crop excess transparent canvas, leaving a small margin for clean rotation.
    alpha = rgba.getchannel("A").point(lambda v: 255 if v > 20 else 0)
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("Cutout is empty")
    margin = 8
    rgba = rgba.crop((max(0, bbox[0] - margin), max(0, bbox[1] - margin),
                      min(rgba.width, bbox[2] + margin),
                      min(rgba.height, bbox[3] + margin)))
    output = io.BytesIO()
    rgba.save(output, "PNG")
    return output.getvalue()


def _reference_for_character(job_dir: Path, character_id: str | None,
                             source: Path | None) -> Path | None:
    if source is not None:
        source = Path(source).expanduser().resolve()
        if not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Character reference must be an existing image under 20 MB")
        _load_image_bytes(source.read_bytes())
        return source
    if not character_id:
        return None
    from historyforgeai.infrastructure.persistence.characters import CharacterRegistry
    registry = CharacterRegistry(job_dir.parent.parent / "characters")
    character = registry.get(character_id)
    if not character.approved or not character.canonical_image:
        raise ValueError("Character reference must be approved in the character registry")
    reference = Path(character.canonical_image).expanduser().resolve()
    if not reference.is_file():
        raise FileNotFoundError(reference)
    _load_image_bytes(reference.read_bytes())
    return reference


def _prompts(shot, description: str, mode: str) -> dict[str, str]:
    character = description.strip() or (", ".join(shot.character_ids) or "historical Indian warrior")
    scene = shot.visual_description.strip()
    base = f"{STYLE} Character: {character}. Scene context: {scene}. "
    prompts = {
        "whole": base + "Full-body single character, front three-quarter view, isolated, "
                 "transparent background, full figure visible, no scenery or other people.",
        "background": f"{STYLE} Detailed illustrated environment only: {scene}. "
                      "Vertical 9:16 composition. No characters, no text.",
    }
    if mode == "body-arm":
        prompts["body"] = (base + "Using the supplied character reference, return ONLY the full-body "
                           "character with their sword-holding arm removed, and naturally complete the clothing "
                           "underneath. Same costume and pose. Transparent background. No loose parts.")
        prompts["arm"] = (base + "Using the supplied character reference, return ONLY the character's "
                          "detached sword-holding arm with its sleeve and sword, from shoulder to weapon tip. "
                          "Match costume and illustration style precisely. Transparent background. "
                          "Do not include a torso, head, other arm, or scenery.")
    return prompts


def _default_spec(scene_index: int, mode: str) -> dict:
    """All prepared assets publish the new puppet-rig v2 format, never layers."""
    root = f"animation/assets/scene_{scene_index:02d}"
    if mode == "puppet":
        from historyforgeai.application.services.puppet_templates import puppet_template
        return puppet_template(scene_index)
    if mode == "whole":
        return {"version": 2, "parts": [{
            "id": "character", "asset": f"{root}/whole.png",
            "x": 0.5, "y": 0.64, "width": 0.62, "pivot": [0.5, 0.5], "z": 1,
            "keyframes": [
                {"t": 0, "dx": -0.03, "scale": 1, "easing": "linear"},
                {"t": 1, "dx": 0.03, "scale": 1.04, "easing": "ease_in_out"},
            ],
        }]}
    if mode == "body-arm":
        return {"version": 2, "parts": [
            {
                "id": "character_body", "asset": f"{root}/body.png",
                "x": 0.5, "y": 0.64, "width": 0.62, "z": 1,
                "keyframes": [
                    {"t": 0, "scale": 1, "easing": "linear"},
                    {"t": 1, "scale": 1.03, "easing": "ease_in_out"},
                ],
            },
            {
                "id": "sword_arm", "asset": f"{root}/arm.png",
                "parent": "character_body",
                "x": 0.62, "y": 0.5, "width": 0.24,
                "pivot": [0.18, 0.12], "z": 2,
                "keyframes": [
                    {"t": 0, "rotation_deg": -35, "easing": "linear"},
                    {"t": 0.45, "rotation_deg": 65, "easing": "back_out"},
                    {"t": 1, "rotation_deg": 65, "easing": "hold"},
                ],
            },
        ]}
    raise ValueError(f"Unknown puppet asset mode: {mode}")


def _draft_dir(job_dir: Path, scene_index: int) -> Path:
    return Path(job_dir) / "animation" / "drafts" / f"scene_{scene_index:02d}"


def load_asset_draft(job_dir: Path, scene_index: int) -> AssetDraft | None:
    path = _draft_dir(job_dir, scene_index) / "manifest.json"
    return AssetDraft.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None


def prepare_scene_assets(
    job_dir: Path, scene_index: int, *,
    provider: Literal["manual", "gemini", "openai"] = "manual",
    mode: Literal["whole", "body-arm", "puppet"] = "whole",
    source: Path | None = None,
    arm_source: Path | None = None,
    character_id: str | None = None,
    description: str = "",
    model: str | None = None,
    allow_paid: bool = False,
    image_budget_usd: float | None = None,
    remove_background: bool = False,
    generate_background: bool = False,
    replace_draft: bool = False,
    generator=None,
) -> AssetDraft:
    """Prepare *unapproved* PNG cutouts. Never writes a live Blender spec.

    For body-arm hosted generation: one reference character + two reference-guided edits.
    Their geometry may be inconsistent; review alignment before approving.
    """
    job_dir = Path(job_dir).resolve()
    if provider not in ("manual", "gemini", "openai") or mode not in ("whole", "body-arm", "puppet"):
        raise ValueError("Unsupported provider or cutout mode")
    if not isinstance(scene_index, int) or scene_index < 1:
        raise ValueError("Scene index must be positive")
    if mode == "puppet" and provider != "manual":
        raise ValueError("12-part puppet import currently requires a manually prepared PNG directory; AI parts-sheet separation is not implemented")
    if provider in ("gemini", "openai") and not allow_paid:
        raise ValueError("Hosted image generation requires explicit --allow-paid")
    if generate_background and (provider == "manual" or not allow_paid):
        raise ValueError("Background generation requires --provider gemini/openai --allow-paid")
    if provider == "manual" and (source is None or (mode == "body-arm" and arm_source is None)):
        raise ValueError("Manual mode needs --source and, for body-arm, --arm-source")
    board = load(job_dir / "storyboard.json")
    shot = next((s for s in board.shots if s.scene_index == scene_index), None)
    if shot is None:
        raise ValueError(f"Scene {scene_index} not found in storyboard")
    target = _draft_dir(job_dir, scene_index)
    if target.exists() and not replace_draft:
        raise FileExistsError("Draft exists; approve/reject it or pass --replace-draft to regenerate")
    reference = None if mode == "puppet" else _reference_for_character(job_dir, character_id, source)
    prompts = _prompts(shot, description, mode)
    from historyforgeai.application.services.image_api_budget import (
        preflight_image_budget, reserve_image_request,
    )
    if provider == "gemini":
        from historyforgeai.infrastructure.images.gemini_cutout import (
            gemini_image, DEFAULT_GEMINI_IMAGE_MODEL,
        )
        model = model or os.getenv("GEMINI_IMAGE_MODEL", DEFAULT_GEMINI_IMAGE_MODEL)
        generate = generator or gemini_image
    elif provider == "openai":
        model = model or os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
        generate = generator or _openai_image
    else:
        generate = None

    if provider != "manual":
        expected_calls = (1 if mode == "whole" else (2 if reference else 3))
        expected_calls += int(generate_background)
        preflight_image_budget(job_dir, provider, expected_calls, image_budget_usd)

    def generate_with_budget(prompt, ref, transparent, selected_model):
        reserve_image_request(job_dir, provider, selected_model, image_budget_usd)
        return generate(prompt, ref, transparent, selected_model)

    staging = target.with_name(target.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    files = {}
    hashes = {}
    background_candidate = None
    try:
        if provider == "manual":
            if mode == "puppet":
                from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
                folder = Path(source).expanduser().resolve()
                if not folder.is_dir():
                    raise ValueError("Puppet mode needs --source DIRECTORY containing 12 transparent PNGs")
                items = {name: folder / f"{name}.png" for name in PUPPET_PARTS}
            else:
                items = {"whole": reference} if mode == "whole" else {"body": reference, "arm": arm_source}
            for name, path in items.items():
                path = Path(path).expanduser().resolve()
                if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError(f"Invalid or oversized {name} image")
                data = path.read_bytes()
                output = staging / f"{name}.png"
                output.write_bytes(_transparent_png(data, remove_background))
                files[name] = output.name
                hashes[name] = _hash(output)
        else:
            if mode == "whole":
                raw = generate_with_budget(prompts["whole"], reference, True, model)
                output = staging / "whole.png"
                output.write_bytes(_transparent_png(raw, remove_background))
                files["whole"] = output.name
                hashes["whole"] = _hash(output)
            else:
                # Generate a consistent reference first when no approved one exists.
                if reference is None:
                    raw_reference = generate_with_budget(prompts["whole"], None, True, model)
                    reference = staging / "reference.png"
                    reference.write_bytes(_transparent_png(raw_reference, remove_background))
                for name in ("body", "arm"):
                    raw = generate_with_budget(prompts[name], reference, True, model)
                    output = staging / f"{name}.png"
                    output.write_bytes(_transparent_png(raw, remove_background))
                    files[name] = output.name
                    hashes[name] = _hash(output)
        # Only after successful generation do we create/replace the draft.
        draft = AssetDraft(
            scene_index=scene_index, mode=mode, provider=provider, model=model,
            character_id=character_id, prompts=prompts, files=files, hashes=hashes,
            notes=("12-part puppet imported; review each joint, overlap and pivot in the rig JSON. "
                   "No automatic joint detection or hidden-area reconstruction." if mode == "puppet" else
                   "Experimental AI part separation: align arm/shoulder before approval." if mode == "body-arm" else
                   "Single-part puppet: no independently moving joints."),
        )
        (staging / "manifest.json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
        if generate_background:
            # Background is a *separate* storyboard candidate, always pending review.
            from historyforgeai.application.services.image_candidates import create_candidate
            temp = target / "background.png"
            temp.write_bytes(generate_with_budget(prompts["background"], None, False, model))
            try:
                background_candidate = str(create_candidate(job_dir, scene_index, "manual", source=temp))
            finally:
                temp.unlink(missing_ok=True)
            draft.background_candidate = background_candidate
            (target / "manifest.json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
        create_draft_preview(job_dir, scene_index)
        return draft
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def create_draft_preview(job_dir: Path, scene_index: int, width: int = 360,
                         height: int = 640) -> Path:
    """Composite approximate first-frame cutouts for review without Blender."""
    job_dir = Path(job_dir).resolve()
    draft = load_asset_draft(job_dir, scene_index)
    if draft is None:
        raise FileNotFoundError("No cutout draft to preview")
    if width <= 0 or height <= 0:
        raise ValueError("Preview size must be positive")
    board = load(job_dir / "storyboard.json")
    shot = next((s for s in board.shots if s.scene_index == scene_index), None)
    bg_path = Path(shot.candidate_image) if shot and shot.candidate_image else None
    if bg_path and bg_path.is_file():
        with Image.open(bg_path) as source:
            background = ImageOps.fit(source.convert("RGBA"), (width, height),
                                      method=Image.Resampling.LANCZOS)
    else:
        background = Image.new("RGBA", (width, height), (40, 51, 68, 255))
    parts = sorted(_default_spec(scene_index, draft.mode)["parts"],
                   key=lambda part: part["z"])
    for part in parts:
        name = Path(part["asset"]).stem
        asset = _draft_dir(job_dir, scene_index) / draft.files[name]
        with Image.open(asset) as source:
            sprite = source.convert("RGBA")
        first = (part.get("keyframes") or [{}])[0]
        scale = first.get("scale", 1.0)
        px_width = max(1, round(width * part["width"] * scale))
        px_height = max(1, round(px_width * sprite.height / sprite.width))
        sprite = sprite.resize((px_width, px_height), Image.Resampling.LANCZOS)
        pivot = part.get("pivot", [0.5, 0.5])
        x = round((part["x"] + first.get("dx", 0)) * width)
        y = round((part["y"] + first.get("dy", 0)) * height)
        surface = Image.new("RGBA", (width, height))
        surface.paste(sprite, (round(x - px_width * pivot[0]),
                               round(y - px_height * pivot[1])))
        rotation = first.get("rotation_deg", 0)
        if rotation:
            surface = surface.rotate(rotation, center=(x, y),
                                     resample=Image.Resampling.BICUBIC)
        background = Image.alpha_composite(background, surface)
    output = _draft_dir(job_dir, scene_index) / "preview.png"
    background.convert("RGB").save(output, "PNG")
    return output


def approve_scene_assets(job_dir: Path, scene_index: int) -> Path:
    """Publish reviewed cutouts and a Blender scene spec with content hashes."""
    job_dir = Path(job_dir).resolve()
    draft_dir = _draft_dir(job_dir, scene_index)
    draft = load_asset_draft(job_dir, scene_index)
    if draft is None or draft.status != "pending_review":
        raise ValueError("No pending cutout draft to approve")
    live = job_dir / "animation" / f"scene_{scene_index:02d}.json"
    if live.is_file() and json.loads(live.read_text(encoding="utf-8")).get("version") == 3:
        raise ValueError("This scene uses multi-character v3; use the puppets builder instead")
    # Verify the entire draft before changing the live animation.
    for name, filename in draft.files.items():
        source = (draft_dir / filename).resolve()
        if not source.is_relative_to(draft_dir.resolve()) or not source.is_file():
            raise ValueError("Draft contains invalid file paths")
        if _hash(source) != draft.hashes.get(name):
            raise ValueError("Draft asset changed after preparation; regenerate it")
        _transparent_png(source.read_bytes(), remove_background=False)
    from historyforgeai.infrastructure.rendering.blender_2d import PuppetRig
    spec = _default_spec(scene_index, draft.mode)
    PuppetRig.model_validate(spec)
    assets = job_dir / "animation" / "assets" / f"scene_{scene_index:02d}"
    assets.mkdir(parents=True, exist_ok=True)
    for name, filename in draft.files.items():
        shutil.copyfile(draft_dir / filename, assets / f"{name}.png")
    spec_path = job_dir / "animation" / f"scene_{scene_index:02d}.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    approved_dir = job_dir / "animation" / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "scene_index": scene_index, "spec_sha256": _hash(spec_path),
        "asset_sha256": {name: _hash(assets / f"{name}.png") for name in draft.files},
    }
    (approved_dir / f"scene_{scene_index:02d}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")
    draft.status = "approved"
    (draft_dir / "manifest.json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return spec_path


def update_approved_scene_spec(job_dir: Path, scene_index: int, spec_text: str) -> Path:
    """Explicitly review and reapprove changed transforms without replacing artwork.

    Only existing, previously approved cutout assets may be referenced.
    """
    job_dir = Path(job_dir).resolve()
    record_path = job_dir / "animation" / "approved" / f"scene_{scene_index:02d}.json"
    if not record_path.is_file():
        raise ValueError("Approve cutout assets before editing animation")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    from historyforgeai.infrastructure.rendering.blender_2d import PuppetRig, resolve_cutout_asset
    spec = PuppetRig.model_validate_json(spec_text)
    expected_root = job_dir / "animation" / "assets" / f"scene_{scene_index:02d}"
    allowed = {(expected_root / f"{name}.png").resolve() for name in record["asset_sha256"]}
    for part in spec.parts:
        if resolve_cutout_asset(job_dir, part.asset) not in allowed:
            raise ValueError("Animation may only reference previously approved cutout assets")
    for name, digest in record["asset_sha256"].items():
        asset = expected_root / f"{name}.png"
        if not asset.is_file() or _hash(asset) != digest:
            raise ValueError("Approved cutout changed; prepare and approve a new draft")
    spec_path = job_dir / "animation" / f"scene_{scene_index:02d}.json"
    temp = spec_path.with_suffix(".partial.json")
    try:
        temp.write_text(json.dumps(spec.model_dump(), indent=2), encoding="utf-8")
        temp.replace(spec_path)
    finally:
        temp.unlink(missing_ok=True)
    record["spec_sha256"] = _hash(spec_path)
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return spec_path


def reject_scene_assets(job_dir: Path, scene_index: int) -> None:
    draft = load_asset_draft(job_dir, scene_index)
    if draft is None or draft.status != "pending_review":
        raise ValueError("No pending draft to reject")
    draft.status = "rejected"
    (_draft_dir(job_dir, scene_index) / "manifest.json").write_text(
        draft.model_dump_json(indent=2), encoding="utf-8")


def verify_approved_assets(job_dir: Path, scene_index: int) -> None:
    """Detect modifications to approved Blender assets and spec before rendering."""
    job_dir = Path(job_dir).resolve()
    record_path = job_dir / "animation" / "approved" / f"scene_{scene_index:02d}.json"
    if not record_path.exists():
        spec_path = job_dir / "animation" / f"scene_{scene_index:02d}.json"
        if spec_path.is_file():
            authored = json.loads(spec_path.read_text(encoding="utf-8"))
            if authored.get("version") == 3:
                raise ValueError("Multi-character v3 scenes must be explicitly approved")
        return  # Backwards compatibility for manually authored v2 scenes.
    record = json.loads(record_path.read_text(encoding="utf-8"))
    spec = job_dir / "animation" / f"scene_{scene_index:02d}.json"
    if not spec.is_file() or _hash(spec) != record["spec_sha256"]:
        raise ValueError(f"Scene {scene_index} cutout animation changed after approval")
    if record.get("format") == "puppet-v3":
        from historyforgeai.application.services.motion_library import motion_source_path
        from historyforgeai.infrastructure.rendering.blender_2d import resolve_cutout_asset
        for relative, digest in record["asset_sha256"].items():
            # Only scene-local, approved character images may be hashed.
            prefix = f"animation/assets/scene_{scene_index:02d}/characters/"
            if not relative.startswith(prefix):
                raise ValueError("Invalid approved v3 character asset path")
            path = resolve_cutout_asset(job_dir, relative)
            if _hash(path) != digest:
                raise ValueError(f"Scene {scene_index} character asset changed after approval")
        for name, digest in record.get("motion_sha256", {}).items():
            path = motion_source_path(job_dir, name)
            if path is None or _hash(path) != digest:
                raise ValueError(f"Scene {scene_index} motion {name} changed after approval")
        from historyforgeai.application.services.puppet_timeline import MultiCharacterScene
        spec_v3 = MultiCharacterScene.model_validate_json(spec.read_text(encoding="utf-8"))
        expected_assets = {p.asset for c in spec_v3.characters for p in c.parts}
        if expected_assets != set(record["asset_sha256"]):
            raise ValueError("Approved v3 character asset manifest does not match scene")
        expected_motions = {a.motion for a in spec_v3.timeline
                            if motion_source_path(job_dir, a.motion) is not None}
        if expected_motions != set(record.get("motion_sha256", {})):
            raise ValueError("Approved v3 motion manifest does not match scene")
        return
    for name, digest in record["asset_sha256"].items():
        path = job_dir / "animation" / "assets" / f"scene_{scene_index:02d}" / f"{name}.png"
        if not path.is_file() or _hash(path) != digest:
            raise ValueError(f"Scene {scene_index} cutout asset {name} changed after approval")
