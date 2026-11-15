"""Run experimental Claude-style configurable Blender rig using original Shiva art."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference" / "claude_shiva"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--blender", default="blender")
    p.add_argument("--output-dir", type=Path, default=Path("workspace/claude_rig_demo"))
    p.add_argument("--scene", type=Path, default=REF / "scenes" / "shiva_five_second.json")
    p.add_argument("--assets-only", action="store_true")
    p.add_argument("--no-encode", action="store_true")
    args = p.parse_args()
    out = args.output_dir.resolve()
    art = out / "art"
    art.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(REF / "make_art.py"), str(art)], check=True)
    spec = json.loads(args.scene.read_text(encoding="utf-8"))
    spec["assets_dir"] = str(art.resolve())
    resolved = out / "scene.resolved.json"
    resolved.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    if args.assets_only:
        print("Generated art:", art)
        return
    blender = shutil.which(args.blender)
    if blender is None and Path(args.blender).is_file():
        blender = str(Path(args.blender).resolve())
    if blender is None:
        raise SystemExit("Blender not found; pass --blender PATH")
    frames = out / "frames"
    frames.mkdir(exist_ok=True)
    subprocess.run([blender, "-b", "--python",
                    str(REF / "blender_configurable_rig.py"), "--",
                    str(resolved), str(frames)], check=True)
    count = round(spec["fps"] * spec["duration"])
    if not (frames / "f_0001.png").is_file() or not (frames / f"f_{count:04d}.png").is_file():
        raise RuntimeError("Missing first or last rendered frame")
    if args.no_encode:
        print("Rendered frames:", frames)
        return
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("FFmpeg missing; frames are in " + str(frames))
    video = out / "shiva_configurable_5s.mp4"
    subprocess.run([ffmpeg, "-y", "-framerate", str(spec["fps"]),
                    "-start_number", "1", "-i", str(frames / "f_%04d.png"),
                    "-frames:v", str(count), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    print("Video:", video)


if __name__ == "__main__":
    main()
