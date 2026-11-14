# Blender 2D hierarchical puppet rig (v2)

The **old independent-layer animation schema has been removed**. Every
`animation/scene_XX.json` must use `{"version": 2, "parts": [...]}`.
The FFmpeg still-image renderer, approved storyboard, Hindi TTS, music and
finishing workflow remain unchanged.

## What is implemented

- **Real Blender parent-child joint hierarchy**: moving the torso carries
  attached head, arms and pelvis; rotating the upper arm carries its forearm
  and weapon. Parenting uses joint pivots and bind-pose offsets.
- **Twelve-part puppet template** with torso, head, two upper arms, two
  forearms, pelvis, two thighs, two shins and weapon.
- **Explicit easing** on keyframe transitions: `linear`, `hold`,
  `ease_in`, `ease_out`, `ease_in_out`, `back_out`.
- **Manually separated multi-part PNG import** through CLI or Streamlit
  Step 2.5, with asset previews, SHA-256 approval and editable/reapprovable
  rig JSON.
- **Gemini/OpenAI illustration generation** still supports a single-part
  image or experimental body+arm pair. Both publish v2 puppet specs; the
  body+arm pair now has real parenting.

**Not implemented:** AI parts-sheet separation, automatic detection of
joint positions, reconstruction of covered anatomy, inverse kinematics,
automatic walk cycles, visual drag-and-drop rig editor, narration-driven
motion planning, or automatic effects. The 12-part bind template is an
approximate starting pose, not guaranteed alignment for any illustration.

## Quick 12-part demo

Install Blender 3.6+ and FFmpeg/FFprobe, then:

```bash
python scripts/blender_2d_demo.py
```

This creates twelve simple placeholder transparent PNGs and a v2 rig,
animates a sword-raising motion with head/torso/arm parenting, and writes
`workspace/blender_demo/short.mp4`. The demo art is not production quality.

To inspect the rig without rendering:

```bash
python scripts/blender_2d_demo.py --assets-only
cat workspace/blender_demo/animation/scene_01.json
```

## Prepare your own full puppet

Create a directory containing exactly these named transparent PNGs:

```text
puppet_parts/
  torso.png
  head.png
  upper_arm_l.png
  forearm_l.png
  upper_arm_r.png
  forearm_r.png
  pelvis.png
  thigh_l.png
  shin_l.png
  thigh_r.png
  shin_r.png
  weapon.png
```

Each image must contain **only its intended part**, with transparent
background and enough hidden overlap painted in to rotate without gaps.
You can create these assets manually or with external art tools. **The app
does not yet automatically cut a generated character into these pieces.**

```bash
historyforgeai cutouts prepare --job JOB_ID --scene 1 \
  --provider manual --mode puppet --source ~/Pictures/puppet_parts
historyforgeai cutouts show --job JOB_ID --scene 1
historyforgeai cutouts approve --job JOB_ID --scene 1
```

In Streamlit Step 2.5, choose **Manual → puppet** and upload the 12 named
PNGs. Inspect the composite, approve, then edit the rig JSON and explicitly
reapprove the updated joints/animations. The static composite preview is
approximate and does not calculate animated parent transforms.

### v2 spec format

```json
{
  "version": 2,
  "parts": [
    {
      "id": "torso",
      "asset": "animation/assets/scene_01/torso.png",
      "parent": null,
      "x": 0.50, "y": 0.53, "width": 0.35,
      "pivot": [0.50, 0.35], "z": 3,
      "keyframes": [
        {"t": 0, "rotation_deg": 0, "easing": "linear"},
        {"t": 1, "rotation_deg": -5, "easing": "ease_in_out"}
      ]
    },
    {
      "id": "upper_arm_r",
      "asset": "animation/assets/scene_01/upper_arm_r.png",
      "parent": "torso",
      "x": 0.62, "y": 0.47, "width": 0.16,
      "pivot": [0.35, 0.10], "z": 5,
      "keyframes": [
        {"t": 0, "rotation_deg": 0, "easing": "linear"},
        {"t": 0.55, "rotation_deg": 65, "easing": "back_out"}
      ]
    }
  ]
}
```

- `parent`: another part ID, or `null` for a root. Parents must exist;
  cycles and duplicate IDs are rejected. Multiple independent root puppets
  are permitted for multi-character scenes.
- `x`, `y`: bind-pose joint position as a fraction of the whole video
  canvas, with `(0,0)` at top left.
- `pivot`: joint location within the individual PNG, measured from its
  top-left corner. `[0.5,0.5]` means the image center.
- `width`: rendered image width as a fraction of the canvas width.
- `z`: drawing order; larger is closer to camera.
- `keyframes[].t`: fraction of measured scene duration (0 to 1).
- `rotation_deg` and `scale`: local joint rotation and scale relative
  to its parent.
- `dx`, `dy`: optional offsets **from the bind pose**, in canvas-width
  and canvas-height fractions, interpreted in the parent's local axes.
- `easing`: controls the interpolation **into** that keyframe. `hold`
  means the previous value holds until the destination frame.

The renderer validates all asset paths, PNG transparency and hierarchy
before launching Blender. A reviewed scene can use up to 32 parts.

## Render an approved job

```bash
historyforgeai render --job JOB_ID \
  --generate-audio --scene-audio --visual-style blender-2d
```

The approved storyboard image is the background. Output remains
`workspace/jobs/JOB_ID/short.mp4`, with clips and narration timeline in
the same paths as before. Blender uses headless CPU Cycles (2 samples)
and FFmpeg H.264 encoding. Rendering can be slow on WSL/CPU; try a
4–6-second scene before a complete Short.

**Security/review:** AI images may incur API charges. The estimated
image-request budget is not a real provider billing cap. Rig specs are
validated JSON, not arbitrary Python. Approved cutout assets/specs are
hash-checked before rendering. Generated art and historical claims
require human review.
