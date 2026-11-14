# Automated illustrated asset preparation (Blender 2D)

HistoryForgeAI can now **prepare reviewable illustrated cutouts** before
Blender rendering. There are two independent approval gates:

1. The existing storyboard image review controls the **background**.
2. A new cutout draft review controls the **character PNG layers and animation**.

Generated cutouts are **never** activated by the renderer until you explicitly
approve them. You can reject or regenerate a draft without disturbing a
previously approved animation.

## What works now

| Capability | Status |
| --- | --- |
| Generate a 2D character PNG from an OpenAI image model | Implemented; billed API |
| Generate a background illustration candidate | Implemented; billed API; separately approved |
| Import a manual transparent PNG | Implemented; free |
| Remove an opaque image's background | Optional local rembg; downloads model weights on first use |
| Generate a separate body and sword arm from the same reference | Experimental reference-guided AI edits; requires human visual review |
| Auto-detect shoulder joints / reconstruct hidden anatomy | **Not implemented** |
| Auto-rig a full skeleton / generate natural walking cycles | **Not implemented** |
| Auto-plan arbitrary motion from Hindi narration | **Not implemented**; default keyframe presets |
| Preview, approve, reject, and edit keyframes in Streamlit | Implemented |
| Detect changes to approved cutouts before rendering | Implemented |

OpenAI API image generation is **separate from ChatGPT Plus or Google AI Pro**;
it may incur charges. The project does not yet enforce a spending cap.
Always use the `--allow-paid` flag or the Streamlit billing consent control
before any API request.

## 1. Prepare an existing storyboard

```bash
historyforgeai run --topic "Chandragupta Maurya" --provider gemini --no-render
historyforgeai storyboard --job JOB_ID
```

Review the script as usual. For the background, either upload your own scene
image in Streamlit or generate one alongside the cutout (see below). A new
background candidate is **pending review**; it does not auto-approve.

## 2A. Automatic illustration generation

```bash
# OPENAI_API_KEY must be configured in .env
historyforgeai cutouts prepare \
  --job JOB_ID --scene 1 --provider openai \
  --mode whole --description "Chandragupta Maurya, royal Mauryan armour" \
  --generate-background --allow-paid
```

This generates one transparent character cutout and one illustrated
background candidate. The character is given a simple animated drift/scale
preset, while the background is sent to the existing storyboard review.

**For separate moving body and sword arm**, choose the experimental mode:

```bash
historyforgeai cutouts prepare \
  --job JOB_ID --scene 1 --provider openai \
  --mode body-arm --description "Chandragupta Maurya in royal armour" \
  --allow-paid
```

Without a character reference, this can make **three** billed image calls:
a full character reference, a body edit, and an arm edit. With an approved
reference it normally makes **two** billed image-edit calls. Adding
`--generate-background` makes one more call. The provider may fail to
preserve character identity or produce a usable detached arm. Check the
results before approval.

You can reuse an approved reference from the character registry:

```bash
historyforgeai cutouts prepare --job JOB_ID --scene 1 \
  --provider openai --mode body-arm \
  --character-id chandragupta --allow-paid
```

Or supply a reference image using `--source ~/Pictures/character.png`.
This guides the image edit but does not guarantee identity preservation.

## 2B. Free/manual asset preparation

```bash
# Already-transparent full-body PNG
historyforgeai cutouts prepare \
  --job JOB_ID --scene 1 --provider manual \
  --mode whole --source ~/Pictures/chandragupta.png

# Opaque image: use local background removal
python -m pip install -e '.[cutouts]'
historyforgeai cutouts prepare \
  --job JOB_ID --scene 1 --provider manual \
  --mode whole --source ~/Pictures/chandragupta.jpg \
  --remove-background

# Independently movable body and arm (both images must be supplied)
historyforgeai cutouts prepare \
  --job JOB_ID --scene 1 --provider manual --mode body-arm \
  --source ~/Pictures/body.png --arm-source ~/Pictures/sword_arm.png
```

`rembg` runs locally and can use CPU, but may download model weights the first
time. It removes backgrounds, **not arms from bodies**. For reliable
body-arm separation, supply already prepared parts or inspect and correct
the experimental AI edits.

## 3. Review and approve

Open the Streamlit storyboard reviewer:

```bash
streamlit run src/historyforgeai/interfaces/storyboard_app.py -- workspace/jobs/JOB_ID
```

Under **Step 2.5 · Illustrated character cutouts**, choose a scene, source
and mode. Review the generated PNGs, approximate composite preview and prompts
before clicking **Approve these cutouts**. The composite is a static first-frame
preview, not a Blender-rendered animation. You can reject drafts or replace them. For approved cutouts,
expand **Adjust animation keyframes** to edit positions, scales, pivot points
and rotations, then explicitly reapprove.

CLI equivalents:

```bash
historyforgeai cutouts show --job JOB_ID --scene 1
historyforgeai cutouts approve --job JOB_ID --scene 1
# Or reject:
historyforgeai cutouts reject --job JOB_ID --scene 1
# After manual edits to a reviewed JSON:
historyforgeai cutouts update-spec --job JOB_ID --scene 1 --file reviewed.json
```

A draft is stored in
`workspace/jobs/JOB_ID/animation/drafts/scene_01/`.
After approval, the live Blender spec and assets appear in:

```text
workspace/jobs/JOB_ID/
  animation/
    scene_01.json
    assets/scene_01/whole.png
    approved/scene_01.json
```

For body-arm, the asset files are `body.png` and `arm.png`.
The approval record contains SHA-256 hashes; rendering fails if an approved
spec or PNG is changed without explicit reapproval.

## 4. Render

Approve the background images and script using the existing storyboard
review, then choose **Blender 2D** in Streamlit's Step 3, or run:

```bash
historyforgeai render --job JOB_ID \
  --generate-audio --scene-audio --visual-style blender-2d
```

Blender animates the approved layers and FFmpeg assembles them with
scene-aligned narration. Output is `workspace/jobs/JOB_ID/short.mp4`.
You can use the existing cinematic finishing step for music and transitions.

## Limitations and editorial checks

- **Generated cutout body parts are not a skeletal rig.** They are separate
  illustrated layers with approximate default shoulder pivots. They may not
  line up. Inspect both the PNGs and a short rendered preview.
- The image API does not guarantee a historically accurate or consistent
  likeness. Treat artwork as a reconstruction, not an archival image.
- If you change the storyboard or script after preparing assets, recheck
  visual alignment. Script and background approvals remain independent.
- This feature does not run in the cloud by itself. On-demand Cloud Run
  deployment is a separate project.
- Do not commit generated artwork, API keys, or unreviewed historical claims.
