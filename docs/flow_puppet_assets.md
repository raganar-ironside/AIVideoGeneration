# Google Flow artwork → Blender puppet assets

The project already supports `prepare_scene_assets(..., mode="whole"|"body-arm"|"puppet")`,
optional `rembg` background removal, reviewed drafts, and approved Blender rendering.

This helper adds **guided 12-part segmentation** for Flow artwork. It does **not**
automatically infer joints, create unseen body parts, or separate a flattened
character reliably without masks.

1. In Flow, generate one front-facing, full-body character in a neutral A-pose,
   with uncrossed arms and separated legs, on a plain background.
2. Download `warrior.png`.
3. In an image editor, paint twelve black/white masks at exactly the same
   resolution as the source, saving them to `masks/`:
   `torso.png`, `head.png`, `upper_arm_l.png`, `forearm_l.png`,
   `upper_arm_r.png`, `forearm_r.png`, `pelvis.png`,
   `thigh_l.png`, `shin_l.png`, `thigh_r.png`, `shin_r.png`,
   `weapon.png`. White = keep; black = discard. Grey = partial alpha.
   For a character without a sword, supply a suitable prop image/mask or
   use the existing whole/body-arm workflow instead.
4. Run:

```powershell
python scripts/flow_puppet_assets.py --image warrior.png --masks masks --output workspace/warrior_parts
```

If the source background is opaque and you need to remove it, install
`pip install -e ".[cutouts]"` and append `--remove-background`.
Background removal is optional and may be slow on CPU.

5. Import the resulting 12 PNGs through the existing manual puppet asset
   preparation workflow, review the draft, adjust pivot coordinates in the
   approved rig, then render with Blender. Mask extraction alone does not
   fix hidden shoulders, knees, overlapping clothing or joint alignment.

The tool writes `manifest.json` with `needs_joint_review` status and never
auto-approves the result. It doesn't require a Google Flow API key.
