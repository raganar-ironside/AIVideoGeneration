"""Tests for guided Google Flow puppet segmentation."""
import pytest
from PIL import Image, ImageDraw

from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
from scripts.flow_puppet_assets import prepare_puppet_assets


def test_exports_twelve_transparent_parts(tmp_path):
    source = tmp_path / "warrior.png"
    Image.new("RGB", (100, 120), "red").save(source)
    masks = tmp_path / "masks"
    masks.mkdir()
    for name in PUPPET_PARTS:
        mask = Image.new("L", (100, 120), 0)
        ImageDraw.Draw(mask).rectangle((30, 30, 70, 90), fill=255)
        mask.save(masks / f"{name}.png")
    output = prepare_puppet_assets(source, masks, tmp_path / "output")
    assert (output / "manifest.json").is_file()
    for name in PUPPET_PARTS:
        with Image.open(output / f"{name}.png") as image:
            assert image.mode == "RGBA"
            assert image.getchannel("A").getextrema() == (0, 255)


def test_missing_mask_fails_without_creating_output(tmp_path):
    source = tmp_path / "warrior.png"
    Image.new("RGB", (100, 120), "red").save(source)
    masks = tmp_path / "masks"
    masks.mkdir()
    with pytest.raises(ValueError, match="Missing or oversized mask"):
        prepare_puppet_assets(source, masks, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_mismatched_mask_fails(tmp_path):
    source = tmp_path / "warrior.png"
    Image.new("RGB", (100, 120), "red").save(source)
    masks = tmp_path / "masks"
    masks.mkdir()
    for name in PUPPET_PARTS:
        Image.new("L", (50, 50), 255).save(masks / f"{name}.png")
    with pytest.raises(ValueError, match="dimensions"):
        prepare_puppet_assets(source, masks, tmp_path / "output")
