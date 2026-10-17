"""Deterministic FFmpeg zoom/pan expressions; no AI video service required."""

def zoompan_filter(width: int, height: int, fps: int, duration: float, style: str = 'zoom_in') -> str:
    frames = max(1, round(duration * fps))
    if style == 'static':
        return f'scale={width}:{height},fps={fps},format=yuv420p'
    if style not in {'zoom_in', 'zoom_out'}:
        raise ValueError(f'Unknown motion style: {style}')
    # Work on a larger image so zoom never exposes borders.
    start, end = (1.0, 1.12) if style == 'zoom_in' else (1.12, 1.0)
    delta = (end-start) / max(frames-1, 1)
    return (f'scale={width*2}:{height*2},'
            f"zoompan=z='{start:.6f}+on*{delta:.9f}':"
            f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
            f'd={frames}:s={width}x{height}:fps={fps},format=yuv420p')
