"""Fast smoke tests: source compatibility and original artwork output."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference" / "claude_shiva"


def test_original_sources_compile():
    for name in ("make_art.py", "build.py"):
        compile((REFERENCE / name).read_text(encoding="utf-8"), name, "exec")


def test_reference_runner_generates_original_art(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "claude_shiva_reference.py"),
         "--assets-only", "--output-dir", str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    manifest = json.loads((tmp_path / "art" / "parts.json").read_text())
    assert {"head", "torso", "rupper", "rfore", "lupper", "lfore",
            "water"}.difference(manifest) == {"water"}
    assert (tmp_path / "art" / "water.png").is_file()
    assert (tmp_path / "art" / "bg.png").is_file()
    assert not (tmp_path / "frames").exists()
    assert "Claude artwork generated" in result.stdout
