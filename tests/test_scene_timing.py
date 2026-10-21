import math
import pytest

from historyforgeai.application.services.timeline import frame_aligned_duration


def test_scene_audio_duration_is_rounded_up_to_whole_video_frames():
    duration = frame_aligned_duration(3.016, fps=24, tail_seconds=0.25)
    assert duration == pytest.approx(79 / 24)
    assert duration >= 3.016 + 0.25
    assert duration - (3.016 + 0.25) < 1 / 24


def test_frame_aligned_duration_rejects_invalid_input():
    for seconds, fps in [(0, 24), (-1, 24), (math.nan, 24), (1, 0)]:
        with pytest.raises(ValueError):
            frame_aligned_duration(seconds, fps)
