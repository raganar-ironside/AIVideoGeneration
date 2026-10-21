"""Tests for music upload, ducking and timing-preserving transitions."""
import hashlib
import json
import shutil
import subprocess

import pytest

from historyforgeai.application.services.cinematic_finishing import (
    find_background_music, finish_video, import_background_music,
)


@pytest.fixture
def media_job(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg is not installed')
    job = tmp_path / 'job'
    clips = job / 'clips'
    clips.mkdir(parents=True)
    durations = [2, 3, 2]
    for i, (color, duration) in enumerate(zip(('red', 'green', 'blue'), durations), 1):
        subprocess.run([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', f'color=c={color}:s=180x320:r=24:d={duration}',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            str(clips / f'scene_{i:02d}.mp4'),
        ], check=True, timeout=30)
    (job / 'timeline.json').write_text(json.dumps([
        {'scene': i, 'duration': duration} for i, duration in enumerate(durations, 1)
    ]), encoding='utf-8')
    concat = job / 'clips.txt'
    concat.write_text(''.join(f"file '{(clips / f'scene_{i:02d}.mp4').resolve()}'\n"
                              for i in range(1, 4)), encoding='utf-8')
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'concat', '-safe', '0', '-i', str(concat),
        '-c', 'copy', str(job / 'silent.mp4'),
    ], check=True, timeout=30)
    for name, frequency in [('narration.wav', 440), ('sample_music.wav', 180)]:
        subprocess.run([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', f'sine=frequency={frequency}:duration=7',
            str(job / name),
        ], check=True, timeout=30)
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', str(job / 'silent.mp4'), '-i', str(job / 'narration.wav'),
        '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
        '-t', '7', str(job / 'short.mp4'),
    ], check=True, timeout=30)
    return job


def _info(path):
    result = subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format',
        '-of', 'json', str(path),
    ], text=True)
    return json.loads(result)


def test_music_upload_rejects_bad_bytes_without_erasing_valid_track(media_job):
    job = media_job
    saved = import_background_music(job, 'music.WAV', (job / 'sample_music.wav').read_bytes())
    assert saved == job / 'assets' / 'background_music.wav'
    assert find_background_music(job) == saved
    previous = saved.read_bytes()
    with pytest.raises(ValueError, match='readable audio'):
        import_background_music(job, 'broken.mp3', b'not music')
    assert saved.read_bytes() == previous
    with pytest.raises(ValueError, match='40 MB'):
        import_background_music(job, 'huge.mp3', b'x' * (40 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match='MP3'):
        import_background_music(job, 'music.exe', b'content')


@pytest.mark.parametrize('transition,duck', [
    ('crossfade', True), ('crossfade', False), ('cut', True),
])
def test_music_and_transitions_keep_duration_and_narration(media_job, transition, duck):
    job = media_job
    original_hash = hashlib.sha256((job / 'short.mp4').read_bytes()).hexdigest()
    voice_hash = hashlib.sha256((job / 'narration.wav').read_bytes()).hexdigest()
    saved_music = import_background_music(job, 'music.wav', (job / 'sample_music.wav').read_bytes())
    output = finish_video(job, saved_music, transition=transition, duck_music=duck)
    assert output.name == 'short_cinematic.mp4'
    info = _info(output)
    video = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
    assert int(video['nb_frames']) == 168
    assert abs(float(info['format']['duration']) - 7) < 0.08
    assert any(stream['codec_type'] == 'audio' for stream in info['streams'])
    assert hashlib.sha256((job / 'short.mp4').read_bytes()).hexdigest() == original_hash
    assert hashlib.sha256((job / 'narration.wav').read_bytes()).hexdigest() == voice_hash
    assert not (job / 'cinematic_transitions.partial.mp4').exists()
    assert not (job / 'short_cinematic.partial.mp4').exists()


def test_crossfade_without_music_preserves_original_audio(media_job):
    job = media_job
    output = finish_video(job, transition='crossfade', transition_seconds=0.4)
    info = _info(output)
    assert any(stream['codec_type'] == 'audio' for stream in info['streams'])
    assert int(next(s for s in info['streams'] if s['codec_type'] == 'video')['nb_frames']) == 168


def test_missing_timeline_fails_without_destroying_existing_cinematic_video(media_job):
    job = media_job
    music = job / 'sample_music.wav'
    previous = finish_video(job, music_path=music, transition='cut')
    original = previous.read_bytes()
    (job / 'timeline.json').unlink()
    with pytest.raises(ValueError, match='Scene timeline missing'):
        finish_video(job, music_path=music, transition='crossfade')
    assert previous.read_bytes() == original


def test_invalid_options_do_not_change_original(media_job):
    job = media_job
    with pytest.raises(ValueError, match='Music volume'):
        finish_video(job, music_volume=1.0)
    with pytest.raises(ValueError, match='Transition must'):
        finish_video(job, transition='wipe')
    with pytest.raises(ValueError, match='Choose a music'):
        finish_video(job, transition='cut')
