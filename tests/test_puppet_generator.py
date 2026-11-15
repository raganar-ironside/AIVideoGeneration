from PIL import Image
import pytest

from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
from historyforgeai.infrastructure.assets.puppet_generator import generate_puppet


@pytest.mark.parametrize("style", ["kathputli", "paper-cutout"])
def test_generates_twelve_transparent_parts(style, tmp_path):
    directory = generate_puppet(style, tmp_path / style)
    assert (directory / "rig_template.json").exists()
    assert (directory / "manifest.json").exists()
    for part in PUPPET_PARTS:
        with Image.open(directory / f"{part}.png") as image:
            assert image.mode == "RGBA"
            assert image.size == (240, 300)
            assert image.getchannel("A").getbbox()


def test_invalid_style(tmp_path):
    with pytest.raises(ValueError, match="Style"):
        generate_puppet("realistic", tmp_path)
