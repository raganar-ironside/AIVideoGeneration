# Phase 3 experiment: procedural Blender warrior

This is an **isolated proof of concept**. It does not replace the Claude Shiva
reference, the configurable rig in PR #34, or the production renderer.

The character is constructed entirely from Blender polygon meshes, ellipses,
emission materials, hierarchical pivot objects and keyframes. It uses **no
Pillow or PNG character inputs**. This is deliberately a basic procedural
illustration to assess the achievable quality and joint mechanics. It is not
yet detailed hand-painted character art, nor a full 3D model.

## Windows PowerShell

From the repository root:

```powershell
git fetch origin
git switch feat/procedural-blender-warrior-20261115
python -m pytest tests/test_blender_warrior_test.py -v
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" -b --python scripts/blender_warrior_test.py -- --preview
```

Preview output: `workspace/blender_warrior/warrior_pose.png`

If the single-frame result looks acceptable, render the 72-frame, 3-second
animation:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" -b --python scripts/blender_warrior_test.py -- --animate
ffmpeg -y -framerate 24 -i workspace/blender_warrior/warrior_%04d.png -c:v libx264 -pix_fmt yuv420p workspace/blender_warrior/warrior_test.mp4
```

Inspect joint connections, sword position, body proportions and overall
illustration quality. Do not merge on the strength of source-only tests;
Blender rendering has **not** been visually QAed on the target Lenovo.

To benchmark runtime, run the preview in PowerShell using `Measure-Command`.
