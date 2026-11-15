# Procedural Maratha puppet artwork (Phase 1)

Generate two art styles without Google Flow, image APIs, Blender or paid services:

```powershell
git pull
.\\.venv\\Scripts\\Activate.ps1
python scripts/puppet_style_demo.py --style both
python -m pytest tests/test_puppet_generator.py -v
```

Outputs are under `workspace/puppet_art/kathputli/` and
`workspace/puppet_art/paper-cutout/`. Each contains twelve transparent
PNG parts, a rig template and a manifest. They are **asset drafts**, not
completed videos. The parts use stylized shapes and approximate pivots.

Phase 2 will add rig alignment, stage artwork, style-specific motion and
two 5-second Blender renders. Review the PNGs before advancing.
