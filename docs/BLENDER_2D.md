# Blender 2D cutout animation (MVP)

HistoryForgeAI can render **real, independently moving 2D illustration layers**
with Blender. The existing FFmpeg renderer remains the default. The Blender
mode does **not** generate artwork, separate body parts, or auto-rig characters:
you supply transparent PNG/WebP layers, such as a body and sword arm, and
animate their position, rotation and scale with keyframes.

## Automatic asset preparation

You can now generate cutout drafts using the OpenAI image API, import a
manual character PNG, or use optional local background removal. Drafts are
previewed and explicitly approved in Streamlit **Step 2.5** before Blender
uses them. Separate body/arm generation is experimental and may require
manual alignment; there is no automatic skeletal rigging.

See [Illustrated asset preparation](ILLUSTRATED_ASSETS.md) for commands,
review workflow, costs, and limitations.

## Install

Blender 3.6+ is recommended, along with FFmpeg and FFprobe. The renderer
uses **Cycles on CPU**, so it can run headlessly without a dedicated GPU.
It may render much more slowly than the FFmpeg still-image mode.

```bash
blender --version
ffmpeg -version
ffprobe -version
```

Install Blender from [blender.org](https://www.blender.org/download/) if it is
not available in WSL/Linux. Ensure the `blender` executable is on `PATH`.

## Try the 6-second prototype first

Generate a self-contained **placeholder** Chandragupta/fortress cutout scene
and render it using Blender:

```bash
python scripts/blender_2d_demo.py
```

Preview `workspace/blender_demo/short.mp4`. The demo draws a simple body,
separate sword arm, and fortress background with Pillow, then animates the
arm in Blender. It is deliberately **not production-quality historical art**.

To inspect the generated PNGs and JSON without installing Blender yet:

```bash
python scripts/blender_2d_demo.py --assets-only
```

## Prepare an approved job

Create or import a Short as usual, approve its script and **all** storyboard
images, and use an approved clean background illustration for each scene.

For a job named `JOB_ID`:

```text
workspace/jobs/JOB_ID/
  scene_plan.json
  storyboard.json
  animation/
    scene_01.json
    assets/
      chandragupta_body.png
      chandragupta_sword_arm.png
```

Each approved storyboard image is used as the **background** of its scene.
If no `animation/scene_XX.json` exists, that scene is rendered with just
its approved background. This allows mixed animated and static scenes.

An example animation spec is in
[`examples/blender_2d_chandragupta.json`](../examples/blender_2d_chandragupta.json).
Copy it to `workspace/jobs/JOB_ID/animation/scene_01.json` and supply the
two referenced transparent assets.

### Spec format

```json
{
  "layers": [
    {
      "id": "commander_body",
      "asset": "animation/assets/chandragupta_body.png",
      "x": 0.5,
      "y": 0.66,
      "width": 0.55,
      "pivot": [0.5, 0.5],
      "z": 1
    },
    {
      "id": "sword_arm",
      "asset": "animation/assets/chandragupta_sword_arm.png",
      "x": 0.62,
      "y": 0.50,
      "width": 0.2,
      "pivot": [0.2, 0.12],
      "z": 2,
      "keyframes": [
        {"t": 0, "rotation_deg": -45},
        {"t": 0.35, "rotation_deg": 70},
        {"t": 1, "rotation_deg": 70}
      ]
    }
  ]
}
```

- `x` and `y`: normalized position of the layer's **pivot** in the
  video, with `(0, 0)` at the **top left** and `(1, 1)` at bottom right.
- `width`: rendered image width as a fraction of the video width.
  The image's aspect ratio is preserved.
- `pivot`: the rotation anchor inside the asset, as fractions measured
  from its top-left corner. Put the arm's pivot at the shoulder.
- `z`: draw order; larger values are in front. Ties preserve list order.
- `keyframes[].t`: fraction of the **actual, measured scene duration**
  from 0 to 1, not fixed seconds. This keeps motion aligned if TTS changes.
- `rotation_deg`: counterclockwise rotation around the pivot.
  Keyframes can also set `x`, `y`, or `scale`; unspecified properties
  retain their previous value.
- Layers are composited with transparent backgrounds. The cutout artwork
  **must** have transparency; a white rectangular background is not usable.

**Reusable assets:** Prefix `asset` with `library:` to reference files
under `workspace/`. Example:
`"library:characters/chandragupta/sword_arm.png"`.
Job-local paths resolve relative to `workspace/jobs/JOB_ID/`.
Paths escaping their permitted roots, including symlink escapes, are rejected.

## Render the video

```bash
historyforgeai render --job JOB_ID \
  --generate-audio --scene-audio \
  --visual-style blender-2d
```

Output remains `workspace/jobs/JOB_ID/short.mp4`, with scene clips in
`clips/scene_XX.mp4` and narration timing in `timeline.json`.
The existing cinematic finishing step can then add music and crossfades
without changing the narration.

The existing `--motion` setting does not control Blender layers: use the
JSON keyframes instead. The Blender MVP does not yet support the FFmpeg
renderer-specific `--subtitles on`, `--title-overlay on`, or
`--watermark on` flags. The existing script/image approvals are still
required; **cutout layers are not individually approved in Streamlit yet**.
Review the assets, licensing and final output yourself before publishing.

## Operational notes

- All cutout assets and animation specs are validated before narration
  synthesis; Blender is invoked with fixed script arguments, not with
  arbitrary user Python.
- Video is rendered at the existing configured resolution and FPS.
  Every scene's frame count is verified before clips are concatenated.
- This is **2D cutout animation**, not automatic lip-sync, hand-drawn
  in-betweening, full-body IK, or generated 3D animation.
- Blender rendering uses CPU and can be resource-intensive. Test a short
  4–6 second scene before rendering an entire Short. For Cloud Run Jobs,
  include Blender in the container image and configure sufficient CPU,
  memory and task timeout. Cloud deployment is a separate feature.
