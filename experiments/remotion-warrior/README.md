# Remotion 2D warrior proof of concept

Standalone React/Remotion experiment. It **does not replace Blender** or alter the production pipeline. All vector character art, fort silhouette, mountains, atmospheric particles and animation are generated in code. No external artwork is required.

## Prerequisites
- Node.js 20+ and npm
- Google Chrome / Chromium available for Remotion's renderer, or allow Remotion to download a compatible browser
- FFmpeg for optional post-processing; Remotion handles standard MP4 output itself

## Windows PowerShell

```powershell
git fetch origin
git switch feat/remotion-warrior-poc-20261116
cd experiments/remotion-warrior
npm install
npm run studio
```

In Remotion Studio select **WarriorShort**. Scrub frames 0–149 to inspect the sword raise, arm joints, parallax, atmospheric particles and camera zoom.

To export a still at frame 75:

```powershell
npm run still
```

To render a five-second, 1080×1920, 30fps MP4:

```powershell
npm run render
```

Outputs: `out/warrior.png` and `out/warrior.mp4`.

## Expectations

This is an intentionally **stylized vector character**, not high-quality hand-painted historical artwork. The purpose is to validate Remotion's deterministic frame rendering, layered SVG articulation, 9:16 output, and browser-based preview before investing in detailed character artwork.

**Validation status:** source committed; `npm install`, TypeScript compilation, Studio preview and MP4 render have **not** been run in the user's environment. Review actual still/video before merging.
