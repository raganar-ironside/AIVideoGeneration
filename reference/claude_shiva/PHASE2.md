# Phase 2: configurable Claude-style rig (experimental)

This is an **additional** renderer, not a replacement for the proven
`build.py`. The original Claude scripts remain untouched.

The new renderer reads a JSON scene containing the canvas coordinates,
parent-child joints, background layers, image overlays, and animation
keyframes. The first test uses the **original Shiva artwork** to isolate
rigging quality from character-art quality.

Run from repository root (PowerShell):

```powershell
python -m pip install numpy Pillow pytest
python -m pytest tests/test_claude_configurable_rig.py -v
python scripts/claude_rig_demo.py --blender "C:\\Program Files\\Blender Foundation\\Blender 5.3\\blender.exe"
```

Output: `workspace/claude_rig_demo/shiva_configurable_5s.mp4`

The 5-second scene intentionally differs from the 2-second original. Its
purpose is to verify **configurable animation**, not exact video parity.
It includes a moving water overlay; the original procedural bubbles are
not yet ported.

Review for correctly connected arms, shoulders, head and torso, and
appropriate layering and motion. Do **not** replace the production renderer
or build a Maratha character until this experimental clip passes visual QA.

Next: create **new high-quality Maratha artwork**, designed on one canvas
with the same joint contract. Do not reuse the rejected blocky assets.
