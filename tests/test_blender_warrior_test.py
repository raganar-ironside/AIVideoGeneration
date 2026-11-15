"""Fast structural tests; Blender itself is not required in CI."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "blender_warrior_test.py"


def test_procedural_warrior_script_compiles():
    ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_warrior_uses_no_external_character_artwork():
    code = SOURCE.read_text(encoding="utf-8")
    assert "bpy.data.meshes.new" in code
    assert "bpy.data.materials.new" in code
    assert "bpy.data.objects.new" in code
    assert "bpy.data.images.load" not in code
    assert "PIL" not in code
    assert "right_shoulder" in code
    assert "sword_blade" in code
    assert 'parser.add_argument("--animate"' in code
