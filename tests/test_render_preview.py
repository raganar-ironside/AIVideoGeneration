"""Cross-platform preview infrastructure regression tests."""
import pytest
from historyforgeai.render_preview import (
    PREVIEW, FINAL, RenderProfile, scene_cache_key, file_sha256, find_executable,
)


def test_preview_is_lower_resolution_than_final():
    assert PREVIEW.width * PREVIEW.height < FINAL.width * FINAL.height
    assert PREVIEW.fps == FINAL.fps
    assert PREVIEW.name != FINAL.name


def test_invalid_profile_rejected():
    with pytest.raises(ValueError):
        RenderProfile("bad", 0, 960)


def test_cache_key_deterministic_and_quality_specific():
    spec = {"duration": 6, "actors": ["a"]}
    assets = {"background.png": "hash-a"}
    first = scene_cache_key(spec, assets, PREVIEW, "v3")
    assert first == scene_cache_key(dict(spec), dict(assets), PREVIEW, "v3")
    assert first != scene_cache_key(spec, assets, FINAL, "v3")
    assert first != scene_cache_key(spec, {"background.png": "hash-b"}, PREVIEW, "v3")
    assert first != scene_cache_key({"duration": 7}, assets, PREVIEW, "v3")
    assert first != scene_cache_key(spec, assets, PREVIEW, "v4")


def test_file_hash_changes_with_contents(tmp_path):
    path = tmp_path / "asset.png"
    path.write_bytes(b"first")
    a = file_sha256(path)
    path.write_bytes(b"second")
    assert file_sha256(path) != a


def test_override_path(monkeypatch, tmp_path):
    exe = tmp_path / "blender fake.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("BLENDER_PATH", str(exe))
    assert find_executable("blender", "BLENDER_PATH") == exe.resolve()


def test_missing_override_fails_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv("BLENDER_PATH", str(tmp_path / "missing.exe"))
    with pytest.raises(FileNotFoundError):
        find_executable("blender", "BLENDER_PATH")
