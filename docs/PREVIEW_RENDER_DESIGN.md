# Blender preview → approval → final render

## Platforms
Windows, Linux and WSL2 are supported by the same Python code. Install Blender
3.6+, FFmpeg and FFprobe in the operating system running Python. Blender is
discovered from PATH, BLENDER_PATH, or a standard Windows Blender installation.
FFMPEG_PATH and FFPROBE_PATH override executable lookup.

## Streamlit workflow
1. Approve the script, scene images and cutout assets as before.
2. Generate narration separately before preview if you need synchronized audio.
3. In Step 3.5 click **Generate / refresh Blender preview**.
4. Review `short_preview.mp4` (540×960, 24 FPS), then click **Approve current Blender preview**.
5. Render in Step 3 using Blender 2D. This reuses existing narration and renders
   full-resolution clips. If scene inputs changed, preview approval is rejected.
6. Edit a scene and regenerate the preview; unchanged scene clips are cached.
   Preview and final caches are isolated.

CLI:
```bash
historyforgeai render --job JOB_ID --visual-style blender-2d --preview
historyforgeai render --job JOB_ID --visual-style blender-2d
```

Preview mode does not synthesize audio. Existing `narration.wav` is reused.
Do not use `--generate-audio` or `--scene-audio` with `--preview`.
After a preview exists, final Blender rendering requires its explicit approval
and disallows scene-audio regeneration, which could change the timeline.

## Cache and approval
Scene clips are cached by validated Blender payload, image-content SHA-256,
render profile, and renderer/encoding version. Preview clips live in
`preview_clips/`; final clips remain in `clips/`. Changed inputs cause
individual scenes to rerender. The final assembly is recreated each run.
Approval records bind the preview's hash to the current scene fingerprint.
An edited scene or replaced preview invalidates approval.

## Known limitations
- No automatic live viewport streaming; preview is a lower-resolution MP4.
- Blender scene renderer still uses its existing CPU Cycles samples.
- Native Windows and WSL2 Blender integration tests require installed binaries;
  CI currently runs Python unit and syntax checks only.
- The original no-preview CLI final render remains supported for compatibility;
  the approval gate applies once a preview has been generated.
- Speech must be generated before preview if synchronized audio is required.
