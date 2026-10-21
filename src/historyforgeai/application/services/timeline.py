import math

from historyforgeai.domain.models import ShortPlan

def build_timeline(plan: ShortPlan, measured_durations: list[float] | None = None) -> list[dict]:
    if measured_durations is not None and len(measured_durations) != len(plan.scenes):
        raise ValueError('Audio durations must match scene count')
    elapsed = 0.0
    result = []
    for i, scene in enumerate(plan.scenes):
        duration = measured_durations[i] if measured_durations is not None else scene.duration_seconds
        if duration <= 0:
            raise ValueError('Scene duration must be positive')
        result.append({'scene': scene.index, 'start': round(elapsed, 3), 'end': round(elapsed + duration, 3),
                       'duration': round(duration, 3), 'narration': scene.narration,
                       'image_path': scene.image_path, 'character_ids': scene.character_ids})
        elapsed += duration
    return result


def frame_aligned_duration(audio_seconds: float, fps: int, tail_seconds: float = 0.25) -> float:
    """Round audio plus a short pause UP to a whole number of video frames."""
    if not math.isfinite(audio_seconds) or audio_seconds <= 0 or fps <= 0 or tail_seconds < 0:
        raise ValueError('Audio duration and FPS must be positive and finite')
    return math.ceil((audio_seconds + tail_seconds) * fps - 1e-9) / fps
