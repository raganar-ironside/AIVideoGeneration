"""Multi-character scene v3 and deterministic, shared-clock motion compilation.

The authored JSON contains character instances and a timeline. At render time
it is flattened into v2 parented Blender joints; no changes to Blender's
trusted Python script or FFmpeg output contract are necessary.
"""
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from historyforgeai.infrastructure.rendering.blender_2d import PuppetPart, PuppetRig
from historyforgeai.application.services.motion_library import load_motion


class CharacterInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,23}$")
    x: float = Field(default=0.5, ge=-1, le=2)
    y: float = Field(default=0.5, ge=-1, le=2)
    scale: float = Field(default=1, gt=0, le=3)
    depth: int = Field(default=0, ge=-5, le=5)
    parts: list[PuppetPart] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_rig(self):
        PuppetRig(version=2, parts=self.parts)
        if any(part.keyframes for part in self.parts):
            raise ValueError("Version 3 parts use timeline actions, not embedded part keyframes")
        return self


class MotionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character: str
    motion: str = Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")
    start: float = Field(ge=0, le=120)
    duration: float = Field(gt=0, le=120)
    repeat: int = Field(default=1, ge=1, le=12)
    intensity: float = Field(default=1, ge=0.1, le=2)
    direction: Literal[-1, 1] = 1
    distance: float = Field(default=0, ge=0, le=2)


class MultiCharacterScene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[3]
    characters: list[CharacterInstance] = Field(min_length=1, max_length=8)
    timeline: list[MotionAction] = Field(default_factory=list, max_length=96)

    @model_validator(mode="after")
    def validate_timeline(self):
        ids = [c.id for c in self.characters]
        if len(set(ids)) != len(ids):
            raise ValueError("Character IDs must be unique")
        if sum(len(c.parts) for c in self.characters) > 96:
            raise ValueError("A scene supports at most 96 puppet parts")
        for action in self.timeline:
            if action.character not in ids:
                raise ValueError(f"Unknown timeline character {action.character!r}")
        for character_id in ids:
            actions = sorted(
                (a for a in self.timeline if a.character == character_id),
                key=lambda a: a.start,
            )
            for prev, current in zip(actions, actions[1:]):
                if current.start < prev.start + prev.duration - 1e-7:
                    raise ValueError(f"Overlapping actions for {character_id!r}; use sequential clips")
        return self


def compile_multi_character_scene(
    spec: MultiCharacterScene, job_dir: Path, duration: float,
) -> list[dict]:
    """Compile independent characters and motions to Blender joint keyframes.

    Non-root joint tracks return to their neutral pose. Root translations
    accumulate across consecutive clips so walking never teleports back.
    Different characters share the same scene clock and may act simultaneously.
    """
    if duration <= 0:
        raise ValueError("Scene duration must be positive")
    for action in spec.timeline:
        if action.start + action.duration > duration + 1e-6:
            raise ValueError(
                f"{action.character}: {action.motion} ends at "
                f"{action.start + action.duration:.2f}s, after scene duration {duration:.2f}s"
            )
    result = []
    for character in spec.characters:
        part_ids = {part.id for part in character.parts}
        root_ids = [part.id for part in character.parts if part.parent is None]
        timeline = sorted(
            (a for a in spec.timeline if a.character == character.id),
            key=lambda a: a.start,
        )
        # Per-joint absolute scene time -> merged pose properties. Rounding
        # removes floating-point noise at adjacent clip boundaries.
        joint_frames: dict[str, dict[float, dict]] = {p.id: {} for p in character.parts}
        root_x = 0.0
        root_y = 0.0

        def add(part_id, seconds, properties, easing):
            time = round(min(1.0, seconds / duration), 9)
            frame = joint_frames[part_id].setdefault(time, {"t": time})
            frame.update(properties)
            frame["easing"] = easing

        for action in timeline:
            clip = load_motion(job_dir, action.motion)
            missing = set(clip.tracks) - part_ids - {"root"}
            if missing:
                raise ValueError(
                    f"Motion {action.motion!r} needs missing joints "
                    f"{', '.join(sorted(missing))} in character {character.id!r}"
                )
            segment = action.duration / action.repeat
            for cycle in range(action.repeat):
                base_x, base_y = root_x, root_y
                origin = action.start + cycle * segment
                for joint, poses in clip.tracks.items():
                    for pose in poses:
                        at = origin + pose.t * segment
                        if joint == "root":
                            properties = {
                                "dx": base_x + pose.dx * action.distance * action.direction / action.repeat,
                                "dy": base_y + pose.dy * action.intensity,
                            }
                            for root in root_ids:
                                add(root, at, properties, pose.easing)
                        else:
                            properties = {
                                "dx": pose.dx * action.intensity,
                                "dy": pose.dy * action.intensity,
                                "rotation_deg": pose.rotation_deg * action.intensity,
                                "scale": 1 + (pose.scale - 1) * action.intensity,
                            }
                            add(joint, at, properties, pose.easing)
                if "root" in clip.tracks:
                    last = clip.tracks["root"][-1]
                    root_x += last.dx * action.distance * action.direction / action.repeat
                    root_y += last.dy * action.intensity

        for order, part in enumerate(character.parts):
            data = part.model_dump()
            data["id"] = f"{character.id}__{part.id}"
            data["parent"] = f"{character.id}__{part.parent}" if part.parent else None
            data["x"] = character.x + (part.x - 0.5) * character.scale
            data["y"] = character.y + (part.y - 0.5) * character.scale
            data["width"] = part.width * character.scale
            data["z"] = character.depth * 20 + part.z
            data["keyframes"] = [
                joint_frames[part.id][time] for time in sorted(joint_frames[part.id])
            ]
            if len(data["keyframes"]) > 240:
                raise ValueError(f"Too many compiled keyframes for {data['id']}")
            result.append(data)
    return result
