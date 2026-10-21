"""Non-destructive cinematic post-processing of an already synchronized Short."""
import json
import math
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

MUSIC_EXTENSIONS = {'.mp3', '.wav', '.m4a'}
MAX_MUSIC_BYTES = 40 * 1024 * 1024


def _probe(path: Path) -> dict:
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format',
         '-of', 'json', str(path)], capture_output=True, text=True, check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def _stream(probe: dict, kind: str) -> dict | None:
    return next((s for s in probe.get('streams', []) if s.get('codec_type') == kind), None)


def find_background_music(job_dir: Path) -> Path | None:
    assets = Path(job_dir) / 'assets'
    for ext in sorted(MUSIC_EXTENSIONS):
        candidate = assets / f'background_music{ext}'
        if candidate.is_file():
            return candidate
    return None


def import_background_music(job_dir: Path, filename: str, content: bytes) -> Path:
    """Validate a browser upload with ffprobe before replacing a saved music file."""
    if not shutil.which('ffprobe'):
        raise RuntimeError('ffprobe is required (sudo apt install ffmpeg)')
    extension = Path(filename).suffix.lower()
    if extension not in MUSIC_EXTENSIONS:
        raise ValueError('Music must be MP3, WAV or M4A')
    if not content or len(content) > MAX_MUSIC_BYTES:
        raise ValueError('Music must be nonempty and at most 40 MB')
    assets = Path(job_dir).resolve() / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    staging = assets / 'background_music.partial'
    destination = assets / f'background_music{extension}'
    try:
        staging.write_bytes(content)
        if not _stream(_probe(staging), 'audio'):
            raise ValueError('Uploaded file contains no readable audio')
        staging.replace(destination)
        for ext in MUSIC_EXTENSIONS:
            old = assets / f'background_music{ext}'
            if old != destination:
                old.unlink(missing_ok=True)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise ValueError('Uploaded file is not readable audio') from exc
    finally:
        staging.unlink(missing_ok=True)
    return destination


def _transition_video(job_dir: Path, fps: Fraction, seconds: float,
                      target: Path) -> int:
    timeline_path = job_dir / 'timeline.json'
    if not timeline_path.is_file():
        raise ValueError('Scene timeline missing. Render with --scene-audio first.')
    timeline = json.loads(timeline_path.read_text(encoding='utf-8'))
    if len(timeline) < 2:
        raise ValueError('Crossfade needs at least two scenes')
    if not math.isfinite(seconds) or not 0.2 <= seconds <= 1.0:
        raise ValueError('Crossfade duration must be between 0.2 and 1.0 seconds')
    fps_float = float(fps)
    fade_frames = max(1, round(seconds * fps_float))
    fade_seconds = fade_frames / fps_float
    durations = []
    clips = []
    for scene in timeline:
        duration = float(scene['duration'])
        if not math.isfinite(duration) or duration <= 2 * fade_seconds:
            raise ValueError('Scene too short for this crossfade duration')
        index = int(scene['scene'])
        clip = job_dir / 'clips' / f'scene_{index:02d}.mp4'
        if not clip.is_file():
            raise FileNotFoundError(f'Missing scene clip: {clip}. Render the video again.')
        durations.append(round(duration * fps_float))
        clips.append(clip)
    total_frames = sum(durations)
    filters = []
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
    for clip in clips:
        command.extend(['-i', str(clip)])
    for i in range(len(clips)):
        if i < len(clips) - 1:
            filters.append(f'[{i}:v]tpad=stop_mode=clone:stop_duration={fade_seconds:.6f}[v{i}]')
        else:
            filters.append(f'[{i}:v]null[v{i}]')
    previous = 'v0'
    elapsed_frames = 0
    for i in range(1, len(clips)):
        elapsed_frames += durations[i - 1]
        output = f'x{i}'
        filters.append(
            f'[{previous}][v{i}]xfade=transition=fade:duration={fade_seconds:.6f}:'
            f'offset={elapsed_frames / fps_float:.6f}[{output}]'
        )
        previous = output
    command.extend(['-filter_complex', ';'.join(filters), '-map', f'[{previous}]',
                    '-an', '-frames:v', str(total_frames), '-c:v', 'libx264',
                    '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
                    str(target)])
    subprocess.run(command, check=True, timeout=1200)
    return total_frames


def finish_video(job_dir: Path, music_path: Path | None = None,
                 music_volume: float = 0.15, duck_music: bool = True,
                 transition: str = 'crossfade', transition_seconds: float = 0.4) -> Path:
    """Write short_cinematic.mp4, keeping original short.mp4 and narration unchanged.

    Fade begins at the existing scene boundary; it holds the outgoing image
    briefly while the next image fades in. The next narration still begins
    exactly at its original boundary. No scene duration is added or removed.
    """
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('ffmpeg and ffprobe are required: sudo apt install ffmpeg')
    if transition not in {'crossfade', 'cut'}:
        raise ValueError('Transition must be crossfade or cut')
    if not math.isfinite(music_volume) or not 0 <= music_volume <= 0.4:
        raise ValueError('Music volume must be between 0 and 40%')
    job_dir = Path(job_dir).resolve()
    original = job_dir / 'short.mp4'
    if not original.is_file():
        raise FileNotFoundError('Render short.mp4 before adding cinematic finishing')
    original_info = _probe(original)
    video_stream = _stream(original_info, 'video')
    if video_stream is None:
        raise ValueError('Rendered Short has no video stream')
    duration = float(original_info['format']['duration'])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Rendered Short has invalid duration')
    fps = Fraction(video_stream['avg_frame_rate'])
    if fps <= 0:
        raise ValueError('Rendered Short has invalid frame rate')
    music = Path(music_path).expanduser().resolve() if music_path else None
    if music and (not music.is_file() or not _stream(_probe(music), 'audio')):
        raise ValueError('Music file is missing or has no audio stream')
    if not music and transition == 'cut':
        raise ValueError('Choose a music track or a crossfade transition')
    has_voice = _stream(original_info, 'audio') is not None
    temp_video = job_dir / 'cinematic_transitions.partial.mp4'
    temp_output = job_dir / 'short_cinematic.partial.mp4'
    final = job_dir / 'short_cinematic.mp4'
    try:
        source = original
        if transition == 'crossfade':
            _transition_video(job_dir, fps, transition_seconds, temp_video)
            source = temp_video
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source)]
        # The original video's narration is the source of truth. Never re-synthesize it.
        if has_voice:
            cmd.extend(['-i', str(original)])
        if music:
            cmd.extend(['-stream_loop', '-1', '-i', str(music)])
        cmd.extend(['-map', '0:v:0', '-c:v', 'copy'])
        if music:
            music_input = 2 if has_voice else 1
            fade_out = max(0, duration - 1.0)
            filters = [
                f'[{music_input}:a]aresample=48000,volume={music_volume:.4f},'
                f'atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,'
                f'afade=t=in:st=0:d={min(0.6, duration / 3):.3f},'
                f'afade=t=out:st={fade_out:.3f}:d={min(1.0, duration):.3f}[music]'
            ]
            if has_voice:
                filters.append(
                    f'[1:a]aresample=48000,atrim=duration={duration:.6f},'
                    'asetpts=PTS-STARTPTS' + (',asplit=2[voice][side]' if duck_music else '[voice]')
                )
                if duck_music:
                    filters.append('[music][side]sidechaincompress=threshold=0.03:'
                                   'ratio=6:attack=20:release=400[ducked]')
                    music_label = 'ducked'
                else:
                    music_label = 'music'
                filters.append(f'[voice][{music_label}]amix=inputs=2:duration=first:'
                               'dropout_transition=0:normalize=0[outa]')
                audio_label = 'outa'
            else:
                audio_label = 'music'
            cmd.extend(['-filter_complex', ';'.join(filters), '-map', f'[{audio_label}]',
                        '-c:a', 'aac', '-b:a', '192k'])
        elif has_voice:
            cmd.extend(['-map', '1:a:0', '-c:a', 'copy'])
        cmd.extend(['-t', f'{duration:.6f}', '-movflags', '+faststart', str(temp_output)])
        subprocess.run(cmd, check=True, timeout=1200)
        if not temp_output.is_file() or temp_output.stat().st_size == 0:
            raise RuntimeError('FFmpeg did not produce a cinematic video')
        temp_output.replace(final)
        return final
    finally:
        temp_video.unlink(missing_ok=True)
        temp_output.unlink(missing_ok=True)
