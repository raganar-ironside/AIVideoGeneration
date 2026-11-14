"""Reusable, validated 2D puppet motion clips.

Each clip is a JSON-safe collection of normalized (0..1) poses. A track
named "root" moves the character; other tracks address local rig joints.
No Python expressions, file imports or executable actions are supported.
"""
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


MOTION_NAME = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


class MotionPose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t: float = Field(ge=0, le=1)
    dx: float = Field(default=0, ge=-2, le=2)
    dy: float = Field(default=0, ge=-2, le=2)
    rotation_deg: float = Field(default=0, ge=-360, le=360)
    scale: float = Field(default=1, gt=0, le=10)
    easing: str = "ease_in_out"

    @model_validator(mode="after")
    def valid_easing(self):
        if self.easing not in {"linear", "hold", "ease_in", "ease_out", "ease_in_out", "back_out"}:
            raise ValueError("Unknown motion easing")
        return self


class MotionClip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    description: str = ""
    tracks: dict[str, list[MotionPose]] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_tracks(self):
        for joint, poses in self.tracks.items():
            if joint != "root" and not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", joint):
                raise ValueError(f"Invalid joint name {joint!r}")
            times = [p.t for p in poses]
            if len(times) < 2 or times[0] != 0 or times[-1] != 1 or times != sorted(set(times)):
                raise ValueError(f"Motion {self.name}: {joint} needs ordered unique t=0 and t=1 endpoints")
            for p in (poses[0], poses[-1]) if joint != "root" else (poses[0],):
                if p.dx != 0 or p.dy != 0 or p.rotation_deg != 0 or p.scale != 1:
                    raise ValueError(f"Motion {self.name}: {joint} must start/end in neutral pose")
            if joint == "root" and any(p.rotation_deg != 0 or p.scale != 1 for p in poses):
                raise ValueError("Root track only supports dx/dy translation; animate the torso separately")
        return self


def _poses(values, field="rotation_deg"):
    return [{"t": t, field: value, "easing": "ease_in_out"} for t, value in values]


def _clip(name, description, tracks):
    return MotionClip.model_validate({"name": name, "description": description, "tracks": tracks})


BUILTIN_MOTIONS = {
    "idle": _clip("idle", "Subtle breathing and head movement", {
        "torso": _poses([(0, 0), (.5, 2), (1, 0)]),
        "head": _poses([(0, 0), (.5, -3), (1, 0)]),
    }),
    "walk": _clip("walk", "One walking cycle with root travel", {
        "root": _poses([(0, 0), (.25, .25), (.5, .5), (.75, .75), (1, 1)], "dx"),
        "thigh_l": _poses([(0, 0), (.25, 24), (.5, 0), (.75, -24), (1, 0)]),
        "thigh_r": _poses([(0, 0), (.25, -24), (.5, 0), (.75, 24), (1, 0)]),
        "shin_l": _poses([(0, 0), (.25, -20), (.5, 0), (.75, 10), (1, 0)]),
        "shin_r": _poses([(0, 0), (.25, 10), (.5, 0), (.75, -20), (1, 0)]),
        "upper_arm_l": _poses([(0, 0), (.25, -15), (.5, 0), (.75, 15), (1, 0)]),
        "upper_arm_r": _poses([(0, 0), (.25, 15), (.5, 0), (.75, -15), (1, 0)]),
    }),
    "run": _clip("run", "Fast exaggerated running cycle with root travel", {
        "root": _poses([(0, 0), (.25, .25), (.5, .5), (.75, .75), (1, 1)], "dx"),
        "thigh_l": _poses([(0, 0), (.25, 48), (.5, 0), (.75, -48), (1, 0)]),
        "thigh_r": _poses([(0, 0), (.25, -48), (.5, 0), (.75, 48), (1, 0)]),
        "shin_l": _poses([(0, 0), (.25, -35), (.5, 0), (.75, 20), (1, 0)]),
        "shin_r": _poses([(0, 0), (.25, 20), (.5, 0), (.75, -35), (1, 0)]),
        "upper_arm_l": _poses([(0, 0), (.25, -32), (.5, 0), (.75, 32), (1, 0)]),
        "upper_arm_r": _poses([(0, 0), (.25, 32), (.5, 0), (.75, -32), (1, 0)]),
        "torso": _poses([(0, 0), (.5, -8), (1, 0)]),
    }),
    "point": _clip("point", "Raise right arm and point, then lower", {
        "upper_arm_r": _poses([(0, 0), (.25, 65), (.75, 65), (1, 0)]),
        "forearm_r": _poses([(0, 0), (.25, -30), (.75, -30), (1, 0)]),
        "head": _poses([(0, 0), (.5, 7), (1, 0)]),
    }),
    "sword_raise": _clip("sword_raise", "Raise weapon arm overhead", {
        "upper_arm_r": _poses([(0, 0), (.35, 85), (.8, 85), (1, 0)]),
        "forearm_r": _poses([(0, 0), (.35, -30), (.8, -30), (1, 0)]),
    }),
    "sword_slash": _clip("sword_slash", "Single forward sword swing", {
        "upper_arm_r": _poses([(0, 0), (.25, 75), (.55, -75), (.8, -30), (1, 0)]),
        "forearm_r": _poses([(0, 0), (.25, -25), (.55, 35), (1, 0)]),
        "torso": _poses([(0, 0), (.55, -16), (1, 0)]),
    }),
    "defend": _clip("defend", "Lift both arms defensively", {
        "upper_arm_l": _poses([(0, 0), (.3, -55), (.75, -55), (1, 0)]),
        "upper_arm_r": _poses([(0, 0), (.3, 55), (.75, 55), (1, 0)]),
        "forearm_l": _poses([(0, 0), (.3, 40), (.75, 40), (1, 0)]),
        "forearm_r": _poses([(0, 0), (.3, -40), (.75, -40), (1, 0)]),
    }),
    "bow": _clip("bow", "Bow at the waist", {
        "torso": _poses([(0, 0), (.4, -28), (.75, -28), (1, 0)]),
        "head": _poses([(0, 0), (.4, -12), (.75, -12), (1, 0)]),
    }),
    "react": _clip("react", "Quick recoil and recovery", {
        "torso": _poses([(0, 0), (.2, 17), (.65, -6), (1, 0)]),
        "head": _poses([(0, 0), (.2, -18), (.65, 8), (1, 0)]),
    }),
    "turn": _clip("turn", "Stylized upper-body turn (not true 3D rotation)", {
        "torso": _poses([(0, 0), (.5, 12), (1, 0)]),
        "head": _poses([(0, 0), (.5, 16), (1, 0)]),
    }),
    "jump": _clip("jump", "Vertical jump and landing", {
        "root": _poses([(0, 0), (.2, -.035), (.5, -.13), (.8, -.035), (1, 0)], "dy"),
        "thigh_l": _poses([(0, 0), (.5, 25), (1, 0)]),
        "thigh_r": _poses([(0, 0), (.5, -25), (1, 0)]),
    }),
}


def motion_source_path(job_dir: Path, name: str) -> Path | None:
    """Resolve the selected custom JSON file, or None for a built-in."""
    if not MOTION_NAME.fullmatch(name):
        raise ValueError("Invalid motion name")
    if name in BUILTIN_MOTIONS:
        return None
    job = Path(job_dir).resolve()
    for root in (job / "motions", job.parent.parent / "motions"):
        root = root.resolve()
        path = (root / f"{name}.json").resolve()
        if not path.is_relative_to(root):
            raise ValueError("Motion path escapes the allowed directory")
        if path.is_file():
            return path
    raise ValueError(f"Unknown motion {name!r}; add workspace/motions/{name}.json")


def load_motion(job_dir: Path, name: str) -> MotionClip:
    path = motion_source_path(job_dir, name)
    if path is None:
        return BUILTIN_MOTIONS[name]
    if path.stat().st_size > 64 * 1024:
        raise ValueError("Motion clip exceeds 64 KiB")
    clip = MotionClip.model_validate_json(path.read_text(encoding="utf-8"))
    if clip.name != name:
        raise ValueError("Motion filename and name must match")
    return clip


def available_motions(job_dir: Path) -> list[str]:
    names = set(BUILTIN_MOTIONS)
    job = Path(job_dir).resolve()
    for root in (job / "motions", job.parent.parent / "motions"):
        if root.is_dir():
            for path in root.glob("*.json"):
                if MOTION_NAME.fullmatch(path.stem):
                    names.add(path.stem)
    return sorted(names)
