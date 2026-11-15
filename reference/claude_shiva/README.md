# Claude Shiva — verified reference baseline

This folder contains the **original uploaded** `make_art.py` and `build.py` scripts.
They are preserved without refactoring, so visual parity can be checked before
adapting their architecture into the general AIVideoGeneration renderer.

Run from the repository root (PowerShell):

```powershell
git pull origin main
python -m pip install Pillow numpy pytest
python scripts/claude_shiva_reference.py --assets-only
python -m pytest tests/test_claude_shiva_reference.py -v
python scripts/claude_shiva_reference.py --blender "C:\\Program Files\\Blender Foundation\\Blender 5.3\\blender.exe"
```

Default output: `workspace/claude_shiva_reference/shiva_reference.mp4`.

**Expected**: 48 frames, 24 fps, 720x1280, 2 seconds; the original
Shiva character, mountain backdrop, rising water and bubbles.

The launcher only changes execution paths and MP4 packaging. It does not modify
the original art or Blender scene. No production rendering code is replaced.

Quality gate: visually compare the rendered video to the working standalone
Claude reference. Do not proceed to generalize the art generator until this
comparison succeeds. This PR does not claim a visual match before that check.
