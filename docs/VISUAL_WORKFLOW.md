# Scene-aware visuals and reusable characters

## Create a character library

```bash
historyforgeai characters add --id rama --name 'Shri Rama' --universe ramayana --description 'Approved blue-skinned depiction, bow, royal attire'
historyforgeai characters approve --id rama --image /absolute/path/to/rama_master.png
historyforgeai characters list
```

Generate your master portrait with your preferred AI image service, **review it**, then approve the local image. The application does not yet call an AI image generation API. Each character can be used across many Shorts by referencing the same `character_ids` value in `scene_plan.json`.

## Use characters in scenes

Add `"character_ids": ["rama"]` to a scene. A scene's explicitly assigned `image_path` takes precedence; otherwise the resolver loads the approved canonical character image. This provides pixel-identical character art, not novel poses. For novel poses, generate and approve variants in a future release.

## Synchronization

Use `--scene-audio` to synthesize narration per scene and measure the actual speech duration with ffprobe. The video scene durations are adjusted to measured audio plus a small pause, and `timeline.json` is written. This is **scene-level synchronization**, not word-level forced alignment. Scene-aware visual selection still requires a reviewable plan and correct image selection.

## Visuals

`--motion zoom_in` uses FFmpeg zoompan; `--motion static` disables it. For historical material, image attribution and licences must be reviewed before publishing. AI reconstructions should be disclosed when realistic.

## Future milestones

- Image search ranking based on visual relevance and source provenance
- Human approval workflow for each image and character variant
- Word-level subtitle alignment
- Animated historical maps and optional image-to-video adapters
