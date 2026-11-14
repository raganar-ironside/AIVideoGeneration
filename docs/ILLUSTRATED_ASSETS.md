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
| Generate a 2D character PNG with Gemini Nano Banana | Implemented; default hosted provider, potentially billed API |
| Use OpenAI image generation instead | Implemented; optional alternative |
| Generate a background illustration candidate | Implemented; billed API; separately approved |
| Import a manual transparent PNG | Implemented; free |
| Import a 12-part hierarchical puppet | Implemented; manually prepared PNGs; approved rig v2 |
| Remove an opaque image's background | Optional local rembg; downloads model weights on first use |
| Generate a separate body and sword arm from the same reference | Experimental reference-guided AI edits; requires human visual review |
| Auto-detect shoulder joints / reconstruct hidden anatomy | **Not implemented** |
| Parent joints into a reusable 12-part rig template | Implemented; joints need manual alignment |
| Auto-detect joint positions / generate natural walking cycles | **Not implemented** |
| Auto-plan arbitrary motion from Hindi narration | **Not implemented**; default keyframe presets |
| Preview, approve, reject, and edit keyframes in Streamlit | Implemented |
| Detect changes to approved cutouts before rendering | Implemented |

Gemini API billing is **separate from the Google AI Pro app subscription**.
A Gemini API key is obtained from Google AI Studio; your project must have
access to the selected image model. API requests may be billed, and promotional
credits or quotas are managed by Google.

The app now enforces an **estimated per-job image API budget** (default $1)
and a maximum attempted image request count (default 8). This is **not a
guaranteed financial cap**: actual Google/OpenAI charges can differ from
the configurable estimate. Requests are counted before sending, including
failed calls. Monitor actual provider billing separately. The `--allow-paid`
flag or Streamlit consent is always required for hosted generation.

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
# Set GEMINI_API_KEY in .env (from https://aistudio.google.com/apikey).
# Gemini is the default provider; use --provider openai for the alternative.
historyforgeai cutouts prepare \
  --job JOB_ID --scene 1 --provider gemini \
  --mode whole --description "Chandragupta Maurya, royal Mauryan armour" \
  --generate-background --remove-background \
  --image-budget-usd 1.00 --allow-paid
```

Gemini may return an **opaque** illustration even if prompted for transparency.
The optional `--remove-background` flag uses local `rembg` to prepare the
cutout. Install it with `python -m pip install -e '.[cutouts]'`. Without
background removal, opaque character output is rejected for review.

This generates one transparent character cutout and one illustrated
background candidate. The character is given a simple animated drift/scale
preset, while the background is sent to the existing storyboard review.

**For separate moving body and sword arm**, choose the experimental mode:

```bash
historyforgeai cutouts prepare \
  --job JOB_ID --scene 1 --provider gemini \
  --mode body-arm --description "Chandragupta Maurya in royal armour" \
  --remove-background --image-budget-usd 1.00 --allow-paid
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
  --provider gemini --mode body-arm \
  --character-id chandragupta --remove-background --allow-paid
```

Or supply a reference image using `--source ~/Pictures/character.png`.
This guides the image edit but does not guarantee identity preservation.

### Budget and model configuration

The defaults in `.env` are:

```dotenv
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
IMAGE_JOB_BUDGET_USD=1.00
IMAGE_JOB_MAX_REQUESTS=8
GEMINI_IMAGE_ESTIMATED_USD=0.25
OPENAI_IMAGE_ESTIMATED_USD=0.25
```

These dollar amounts are **editable estimates per attempted image request**,
not official model prices. Model choice, token usage, resolution, and billing
tier can change actual charges. If a model is unavailable, specify one
supported by your AI Studio project with `--model`.

View the ledger for a job:

```bash
historyforgeai cutouts budget --job JOB_ID
```

The budget preflight checks the number of planned image requests before
starting (one for a whole character, two or three for body-arm, plus one
for an optional background). It also checks each attempt immediately before
the API call. A failed call remains counted. To raise the estimated guard,
pass a higher `--image-budget-usd` explicitly. This does **not** configure
a Google Cloud Billing budget or alert.

To use OpenAI instead, set `OPENAI_API_KEY` and pass
`--provider openai`. It uses the same approval and budget checks.

## 2B. Full 12-part puppet (new animation architecture)

The independent-layer Blender format has been **removed**. All approved
animation specs now use `{"version":2,"parts":[...]}` with parent-child
joints and explicit easing. The `whole` and `body-arm` options
still exist as limited **asset inputs** to the new rig engine; only
the 12-part mode allows head, shoulders, elbows, pelvis and legs to
move separately.

For a full rig, prepare **12 separate transparent PNGs** named
`torso.png`, `head.png`, `upper_arm_l.png`, `forearm_l.png`,
`upper_arm_r.png`, `forearm_r.png`, `pelvis.png`, `thigh_l.png`,
`shin_l.png`, `thigh_r.png`, `shin_r.png`, and `weapon.png`.

```bash
historyforgeai cutouts prepare --job JOB_ID --scene 1 \
  --provider manual --mode puppet --source ~/Pictures/puppet_parts
historyforgeai cutouts show --job JOB_ID --scene 1
historyforgeai cutouts approve --job JOB_ID --scene 1
```

Or select **Manual → puppet** in Streamlit Step 2.5 and upload all
12 named files. The template's joint locations are estimates: inspect
and edit `animation/scene_01.json`, then explicitly reapprove the spec.
The static composite preview does not simulate parent-joint rotations.

**Gemini does not yet generate a complete 12-part puppet or parts sheet
automatically.** That requires a separate parts-generation workflow and
joint-alignment work. See [Blender puppet rig v2](BLENDER_2D.md).

## 2C. Other manual asset preparation

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

For body-arm, the asset files are `body.png` and `arm.png`. For full puppets,
all 12 named PNGs are stored under the same scene asset folder.
The approval record contains SHA-256 hashes; rendering fails if an approved
spec or PNG is changed without explicit reapproval.

## 4. Render

Approve the background images and script using the existing storyboard
review, then choose **Blender 2D** in Streamlit's Step 3, or run:

```bash
historyforgeai render --job JOB_ID \
  --generate-audio --scene-audio --visual-style blender-2d
```

Blender animates the approved parented puppet parts and FFmpeg assembles them with
scene-aligned narration. Output is `workspace/jobs/JOB_ID/short.mp4`.
You can use the existing cinematic finishing step for music and transitions.

## Limitations and editorial checks

- **The Blender renderer now has a real parented puppet rig**, but Gemini's
  existing single-part/body-arm image preparation does not generate a full
  12-part rig. The full rig currently requires manually prepared pieces.
  Pivots and overlaps still need human alignment; there is no automatic
  joint detection or hidden-anatomy reconstruction.
- The image API does not guarantee a historically accurate or consistent
  likeness. Treat artwork as a reconstruction, not an archival image.
- If you change the storyboard or script after preparing assets, recheck
  visual alignment. Script and background approvals remain independent.
- This feature does not run in the cloud by itself. On-demand Cloud Run
  deployment is a separate project.
- Do not commit generated artwork, API keys, or unreviewed historical claims.
