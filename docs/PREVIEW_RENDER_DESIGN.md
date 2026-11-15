# Cross-platform preview → approval → final render

Status: **infrastructure foundation only**. The existing CLI and Streamlit app
do not yet use this module. Do not treat this branch as a finished workflow.

## Platform support

Native Windows, Ubuntu and WSL2 use the same Python package. Install Blender
3.6+ and FFmpeg for the environment running the Python process. On Windows,
the helper searches standard Blender Foundation installation folders if
Blender is absent from PATH. On WSL2, install Linux Blender or explicitly set
BLENDER_PATH to a compatible executable; avoid mixing Windows and WSL paths
without conversion.

Optional environment variables:

- `BLENDER_PATH`: absolute path to Blender executable
- `FFMPEG_PATH`: absolute path to FFmpeg executable

## Profiles

- Preview: 540 × 960, 24 FPS, 8 samples
- Final: 1080 × 1920, 24 FPS, 32 samples

Both use identical scene keyframes and timeline duration. Lower resolution
does not guarantee a fixed preview speedup.

## Cache safety

Compute SHA-256 of all scene inputs, including approved cutout images,
backgrounds, animation specifications and any audio affecting clip output.
Include render profile, Blender/renderer version, encoding settings and
other render-affecting settings in the cache key. Preview clips must **never**
satisfy final-render cache lookups.

## Remaining integration work

1. Wire `RenderProfile` into the existing Blender scene renderer.
2. Write preview clips to a separate directory and cache them by content key.
3. Add Streamlit preview player, per-scene regeneration and explicit approval.
4. Invalidate approvals when scene inputs change.
5. Render only approved scenes at final quality; assemble final MP4.
6. Add integration tests on Windows and Ubuntu CI, including Blender smoke tests.
