# Phase 2 — puppet motion comparison

This prototype builds on the Phase 1 procedural puppet PNGs and reuses
the existing Blender 2D renderer. It creates **two 5-second silent MP4s**.

Run from the repository root with the virtual environment active:

```powershell
python scripts/puppet_motion_demo.py --assets-only
python scripts/puppet_motion_demo.py --mode both
```

Expected outputs:

- `workspace/puppet_motion/string-puppet/short.mp4`
- `workspace/puppet_motion/hinged-cutout/short.mp4`

Requirements: Blender, FFmpeg, FFprobe and installed Python dependencies.

The animations are first-pass motion tests. Part alignment, pivots,
hand-to-moustache contact and physically convincing strings still require
visual refinement. String-puppet is a motion preset, not simulated strings.
No audio is generated.
