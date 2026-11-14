# Multi-character puppet scenes and reusable motions (v3)

HistoryForgeAI can now render **several independently animated 2D puppet
characters in one Blender scene**, on one scene-level timeline. It builds on
the v2 parent-child rig; the v2 format and existing single-character cutout
preparation still work.

**Important:** Motion is keyframed 2D puppet animation, not 3D character
animation or automatic choreography. Characters need 12 separated, transparent
PNG parts each. Gemini does not yet split a full character into those parts.

## Try the two-character demo

```bash
python scripts/multi_character_demo.py --assets-only
python scripts/multi_character_demo.py --duration 6
```

This makes two placeholder actors, one walking and attacking, the other
defending at overlapping times. No image API credits are used. The rendered
file is `workspace/multi_character_demo/short.mp4`.

## Add two characters to a real scene

Use an existing job with `scene_plan.json` and an approved scene background.
Prepare two folders with the 12 files:

```text
shivaji_parts/
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
afzal_parts/
  (same 12 filenames, different artwork)
```

```bash
historyforgeai puppets add-character --job JOB_ID --scene 1 \
  --id shivaji --source ~/Pictures/shivaji_parts \
  --x 0.30 --y 0.55 --scale 0.65 --depth 0

historyforgeai puppets add-character --job JOB_ID --scene 1 \
  --id afzal --source ~/Pictures/afzal_parts \
  --x 0.70 --y 0.55 --scale 0.75 --depth 1

historyforgeai puppets add-action --job JOB_ID --scene 1 \
  --character shivaji --motion walk --start 0 --duration 2 \
  --repeat 2 --distance 0.15

historyforgeai puppets add-action --job JOB_ID --scene 1 \
  --character shivaji --motion sword_slash --start 2 --duration 1

historyforgeai puppets add-action --job JOB_ID --scene 1 \
  --character afzal --motion defend --start 2 --duration 1

historyforgeai puppets show --job JOB_ID --scene 1
historyforgeai puppets preview --job JOB_ID --scene 1
historyforgeai puppets approve --job JOB_ID --scene 1

historyforgeai render --job JOB_ID \
  --generate-audio --scene-audio --visual-style blender-2d
```

Before approval, assets and actions live under
`animation/multi_drafts/scene_01/` and **do not affect the approved
scene**. Approval publishes `animation/scene_01.json`, the character
PNG files and hashes. Adding an action after approval creates/updates a
new draft; approve again before it affects rendering.

In **Streamlit Step 2.5**, open *Multi-character puppet scene builder · v3*
to upload each character's 12 PNGs, position the actors, edit joint pivots,
add timeline actions, review a static preview and approve. The preview is
a bind-pose composite, not an animation preview. Render a short clip to
inspect actual motion.

## Built-in motion library

```bash
historyforgeai puppets motions --job JOB_ID
```

| Motion | Effect |
| --- | --- |
| `idle` | Subtle head and torso movement |
| `walk` | Alternating arms and legs with optional travel |
| `run` | Faster, more exaggerated travel cycle |
| `point` | Right arm pointing gesture |
| `sword_raise` | Raise weapon arm |
| `sword_slash` | Single stylized sword attack |
| `defend` | Raise both arms defensively |
| `bow` | Bend torso and head |
| `react` | Recoil and recover |
| `turn` | Stylized head/torso rotation (not a 3D turn) |
| `jump` | Rise and land using root motion |

`--start` and `--duration` are **seconds within the scene**, not
within the whole Short. Actions for different actors may overlap; actions
for the **same actor must not overlap**. Actions for a given actor are
sequenced, and root travel persists between them.

`--repeat` repeats a cycle within its duration. `--intensity` scales
motion, `--direction -1` moves left, and `--distance` controls total
horizontal travel in canvas-width units for clips with a root `dx` track.
For `walk` and `run`, omit `--distance` to walk/run in place.

The actual scene duration can change when narration timing is measured;
a motion ending after the measured scene duration is rejected at render.
Keep a little time margin when planning clips.

## Add any new motion without modifying Python

Save a JSON file at `workspace/motions/salute.json` (reusable across jobs)
or `workspace/jobs/JOB_ID/motions/salute.json` (job-specific override):

```json
{
  "name": "salute",
  "description": "Raise the right hand in salute, then lower it",
  "tracks": {
    "upper_arm_r": [
      {"t": 0, "rotation_deg": 0},
      {"t": 0.3, "rotation_deg": 65, "easing": "back_out"},
      {"t": 0.8, "rotation_deg": 65, "easing": "hold"},
      {"t": 1, "rotation_deg": 0, "easing": "ease_out"}
    ],
    "forearm_r": [
      {"t": 0, "rotation_deg": 0},
      {"t": 0.3, "rotation_deg": -40},
      {"t": 0.8, "rotation_deg": -40, "easing": "hold"},
      {"t": 1, "rotation_deg": 0}
    ]
  }
}
```

Then use `--motion salute` or choose *salute* in Streamlit. Every
non-root joint track must start and finish at the neutral pose, with
ordered `t=0` and `t=1` endpoints. A `root` track can move the
character with `dx`/`dy` and may finish displaced. Joint IDs must
exist in that character's rig. Only JSON data is accepted; there is no
arbitrary Python execution. A custom clip is SHA-256 pinned at approval,
so editing it requires reapproval.

## Authoring format

`animation/scene_01.json` is a **v3 scene**, containing:

```json
{
  "version": 3,
  "characters": [
    {
      "id": "shivaji",
      "x": 0.30, "y": 0.55, "scale": 0.65, "depth": 0,
      "parts": [
        {
          "id": "torso",
          "asset": "animation/assets/scene_01/characters/shivaji/torso.png",
          "parent": null,
          "x": 0.5, "y": 0.53, "width": 0.35,
          "pivot": [0.5, 0.35], "z": 3,
          "keyframes": []
        }
      ]
    }
  ],
  "timeline": [
    {
      "character": "shivaji", "motion": "point",
      "start": 0, "duration": 1.5,
      "repeat": 1, "intensity": 1, "direction": 1, "distance": 0
    }
  ]
}
```

This example illustrates the shape only: for a full rig include all
12 parts and their correct parent relationships.

At render time v3 is compiled into namespaced Blender joints
(`shivaji__torso`, `afzal__torso`, etc.) and a **trusted v2 render
payload**. No custom Python is passed to Blender. Character depth controls
draw order, and each actor has independent parent-child transforms.

### Current limits

- Up to **8 characters** and **96 total parts** per scene; performance
  will vary significantly with character count and CPU.
- No automatic rigging, image separation, foot planting, inverse
  kinematics, physics, collision detection, sword contact or lip-sync.
- No AI text-to-motion planner yet. You select actions and timings;
  the library only supplies repeatable keyframe curves.
- No blending of overlapping actions on the **same character**; plan
  sequential clips instead.
- Static preview is approximate. Test a 4–6-second scene before rendering
  a complete Short.

The Blender renderer still requires Blender 3.6+ and FFmpeg/FFprobe.
