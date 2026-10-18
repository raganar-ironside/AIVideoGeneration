import math
import re
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from historyforgeai.domain.models import ShortPlan
from historyforgeai.infrastructure.rendering.motion import zoompan_filter

class FFmpegRenderer:
    def __init__(self, width=720, height=1280, fps=24, subtitles=False, title_overlay=False, watermark=False):
        self.width, self.height, self.fps = width, height, fps
        self.subtitles = subtitles
        self.title_overlay = title_overlay
        self.watermark = watermark

    def _frame(self, scene, target: Path, title: str):
        w, h = self.width, self.height
        if scene.image_path and Path(scene.image_path).exists():
            try:
                with Image.open(scene.image_path) as original:
                    image = ImageOps.fit(original.convert("RGB"), (w,h), method=Image.Resampling.LANCZOS)
            except Exception:
                image = Image.new("RGB", (w,h), (22,28,40))
        else:
            image = Image.new("RGB", (w,h), (22,28,40))
        if self.title_overlay or self.subtitles or self.watermark:
            draw = ImageDraw.Draw(image, "RGBA")
            fontpath = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            devanagari = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"
            def wrap(text, max_chars=32):
                import textwrap
                return "\n".join(textwrap.wrap(text, max_chars, break_long_words=False))
            if self.title_overlay:
                draw.rectangle((0, 0, w, 190), fill=(0, 0, 0, 175))
                font = ImageFont.truetype(fontpath, 32) if Path(fontpath).exists() else ImageFont.load_default()
                draw.multiline_text((36, 42), wrap(title, 30), font=font, fill="white", spacing=7)
            if self.subtitles:
                draw.rectangle((0, h - 290, w, h - 70), fill=(0, 0, 0, 185))
                font_file = devanagari if Path(devanagari).exists() else fontpath
                font = ImageFont.truetype(font_file, 25) if Path(font_file).exists() else ImageFont.load_default()
                draw.multiline_text((36, h - 240), wrap(scene.narration, 37), font=font, fill="white", spacing=8)
            if self.watermark:
                draw.rectangle((0, h - 70, w, h), fill=(0, 0, 0, 185))
                font = ImageFont.truetype(fontpath, 25) if Path(fontpath).exists() else ImageFont.load_default()
                draw.text((36, h - 55), "HISTORYFORGEAI  •  DRAFT", font=font, fill=(230, 190, 105))
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, quality=90)

    def render(self, plan: ShortPlan, job_dir: str, audio_path: str | None = None, motion: str = "zoom_in") -> str:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg is required: sudo apt install ffmpeg")
        folder = Path(job_dir)
        clips = folder / "clips"
        clips.mkdir(exist_ok=True)
        paths = []
        for scene in plan.scenes:
            frame = clips / f"scene_{scene.index:02d}.jpg"
            clip = clips / f"scene_{scene.index:02d}.mp4"
            self._frame(scene, frame, plan.title)
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-loop","1","-framerate",str(self.fps),
                "-i",str(frame),"-t",str(scene.duration_seconds),"-vf",zoompan_filter(self.width, self.height, self.fps, scene.duration_seconds, motion),
                "-c:v","libx264","-preset","ultrafast","-crf","27","-pix_fmt","yuv420p",str(clip)],
                check=True, timeout=180)
            paths.append(clip)
        concat = folder / "clips.txt"
        concat.write_text("".join(f"file '{p.resolve()}'\n" for p in paths), encoding="utf-8")
        silent = folder / "silent.mp4"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat),
            "-c","copy",str(silent)], check=True, timeout=180)
        output = folder / "short.mp4"
        if audio_path and Path(audio_path).exists():
            duration = sum(s.duration_seconds for s in plan.scenes)
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-i",audio_path,
                "-filter_complex",f"[1:a]apad,atrim=duration={duration:.3f}[a]", "-map","0:v:0","-map","[a]",
                "-c:v","copy","-c:a","aac","-shortest",str(output)],check=True,timeout=180)
        else:
            shutil.copyfile(silent, output)
        return str(output)
