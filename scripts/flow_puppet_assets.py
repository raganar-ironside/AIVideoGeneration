"""Turn a Google Flow character image plus per-part masks into 12 Blender cutouts.

Masks are user-reviewed grayscale PNGs: white selects a body part, black removes it.
This is guided segmentation, not automatic joint detection or occlusion repair.
Usage:
  python scripts/flow_puppet_assets.py --image warrior.png --masks masks/ --output assets/warrior
  python scripts/flow_puppet_assets.py --image warrior.png --masks masks/ --output assets/warrior --remove-background
"""
import argparse
import io
import json
from pathlib import Path

from PIL import Image, ImageChops

from historyforgeai.application.services.puppet_templates import PUPPET_PARTS


def prepare_puppet_assets(image_path: Path, masks_dir: Path, output_dir: Path, *,
                          remove_background: bool = False) -> Path:
    """Export reviewed cutouts without silently fabricating missing limbs.

    Every mask must match the source image dimensions. Output is only written
    after all masks pass validation. The original source is never modified.
    """
    image_path = Path(image_path).resolve()
    masks_dir = Path(masks_dir).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir == masks_dir or output_dir == image_path.parent:
        raise ValueError("Output must be separate from source and masks directories")
    if not image_path.is_file() or image_path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Source image is missing or exceeds 25 MB")
    with Image.open(image_path) as original:
        original.load()
        if original.width > 4096 or original.height > 4096:
            raise ValueError("Source image exceeds 4096 pixels per side")
        source = original.convert("RGBA")
    if remove_background:
        from historyforgeai.application.services.illustrated_assets import _transparent_png
        # _transparent_png crops the image, so use rembg directly to retain mask coordinates.
        try:
            from rembg import remove
        except ImportError as exc:
            raise RuntimeError("Install background removal: pip install -e '.[cutouts]'") from exc
        stream = io.BytesIO()
        source.save(stream, format="PNG")
        with Image.open(io.BytesIO(remove(stream.getvalue()))) as cutout:
            source = cutout.convert("RGBA")
        if source.size != original.size:
            raise ValueError("Background removal changed canvas dimensions")
    masks = {}
    for name in PUPPET_PARTS:
        path = masks_dir / f"{name}.png"
        if not path.is_file() or path.stat().st_size > 25 * 1024 * 1024:
            raise ValueError(f"Missing or oversized mask: {path}")
        with Image.open(path) as mask_file:
            mask_file.load()
            if mask_file.size != source.size:
                raise ValueError(f"Mask dimensions differ from source: {path}")
            mask = mask_file.convert("L")
        if mask.getbbox() is None:
            raise ValueError(f"Mask is empty: {path}")
        masks[name] = mask
    # Prevent writing into the mask directory or overwriting the original image.
    if output_dir == image_path or output_dir.is_relative_to(masks_dir):
        raise ValueError("Output cannot overwrite source or masks")
    output_dir.mkdir(parents=True, exist_ok=True)
    alpha = source.getchannel("A")
    for name, mask in masks.items():
        part = source.copy()
        part.putalpha(ImageChops.multiply(alpha, mask))
        bounds = part.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"No visible pixels after alpha masking: {name}")
        margin = 12
        x0, y0, x1, y1 = bounds
        part = part.crop((max(0, x0-margin), max(0, y0-margin),
                          min(source.width, x1+margin), min(source.height, y1+margin)))
        part.save(output_dir / f"{name}.png")
    manifest = {"source": str(image_path), "parts": list(PUPPET_PARTS),
                "status": "needs_joint_review",
                "notes": "Masks do not reconstruct hidden anatomy. Adjust pivots and alignment before approval."}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Create reviewed Blender puppet PNGs from Flow artwork and masks")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--masks", type=Path, required=True, help="Folder with 12 grayscale PNG masks")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remove-background", action="store_true")
    args = parser.parse_args()
    print("Created puppet assets:", prepare_puppet_assets(
        args.image, args.masks, args.output, remove_background=args.remove_background))


if __name__ == "__main__":
    main()
