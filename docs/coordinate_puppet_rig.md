# Coordinate-based puppet assembly (Phase 2.1)

This integrates the shared-coordinate design from the user-supplied
`make_art.py` and `build.py` references into the existing renderer.
Unlike the earlier approximate rig, all parts are arranged in a common
700×1300 character coordinate system, tightly cropped, and exported with
their exact original bounding box, joint position and normalized pivot.

It retains the existing Blender v2 hierarchy rather than replacing the
rendering pipeline with custom Blender code. No external AI or physics
engine is needed.

From the repository root (Windows PowerShell):

```powershell
python scripts/puppet_motion_demo.py --assets-only
python -m pytest tests/test_coordinate_puppet.py tests/test_puppet_motion_demo.py -v
python scripts/puppet_motion_demo.py --mode both
```

Outputs:
- `workspace/puppet_motion/string-puppet/short.mp4`
- `workspace/puppet_motion/hinged-cutout/short.mp4`
- Each job's `generated_art/<style>/parts.json` records bounding boxes
  and joints for inspection.

**Scope:** Coordinate-based assembly and existing motion presets.
The user-supplied Shiva reference also animated water, bubbles and layered
mountains; those scene effects are not yet ported. The string mode does not
simulate actual strings. Hand-to-moustache contact, art proportions and
render quality still require visual review.

This is a stacked PR and depends on Phase 1 and Phase 2 being merged.
