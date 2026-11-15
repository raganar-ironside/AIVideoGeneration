"""Reproduce Claude's proven Shiva animation without touching the production renderer.

The original make_art.py/build.py remain byte-for-byte separate under
reference/claude_shiva. All generated assets and frames go to --output-dir.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[1] / "reference" / "claude_shiva"


def run_reference(output_dir: Path, blender: str = "blender",
                  assets_only: bool = False, encode: bool = True) -> Path:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "art").mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(REFERENCE / "make_art.py"),
                    str(output_dir / "art")], cwd=output_dir, check=True)
    manifest = output_dir / "art" / "parts.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not data or not (output_dir / "art" / "bg.png").is_file():
        raise RuntimeError("Claude artwork generator did not produce the expected assets")
    print(f"Claude artwork generated: {manifest}", flush=True)
    if assets_only:
        return manifest

    blender_exe = shutil.which(blender)
    if blender_exe is None and Path(blender).is_file():
        blender_exe = str(Path(blender).resolve())
    if blender_exe is None:
        raise RuntimeError("Blender executable not found; supply --blender PATH")
    # The reference build.py intentionally uses relative art/ and frames/ paths.
    # Its working directory MUST be the isolated output folder.
    subprocess.run([blender_exe, "-b", "--python", str(REFERENCE / "build.py")],
                   cwd=output_dir, check=True)
    first_frame = output_dir / "frames" / "f_0001.png"
    last_frame = output_dir / "frames" / "f_0048.png"
    if not first_frame.is_file() or not last_frame.is_file():
        raise RuntimeError("Expected 48-frame Shiva render was not produced")
    print(f"Rendered frames: {output_dir / 'frames'}", flush=True)
    if not encode:
        return output_dir / "frames"
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("FFmpeg not found; frames are available under output/frames")
    video = output_dir / "shiva_reference.mp4"
    subprocess.run([ffmpeg, "-y", "-framerate", "24", "-start_number", "1",
                    "-i", str(output_dir / "frames" / "f_%04d.png"),
                    "-frames:v", "48", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(video)], cwd=output_dir, check=True)
    if not video.is_file():
        raise RuntimeError("FFmpeg did not produce an MP4")
    print(f"Claude reference video: {video}", flush=True)
    return video


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the original Claude Shiva baseline")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("workspace/claude_shiva_reference"))
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--assets-only", action="store_true")
    parser.add_argument("--no-encode", action="store_true")
    args = parser.parse_args()
    run_reference(args.output_dir, args.blender, args.assets_only, not args.no_encode)


if __name__ == "__main__":
    main()
