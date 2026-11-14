"""Blender headless renderer for version-2 hierarchical puppet rigs.

Invoked only by the validated host renderer. No untrusted Python execution.
The pivot anchors form a real parent/child transform hierarchy; the sprite
planes are children of their own pivot anchors.
"""
import json
import math
import sys
from pathlib import Path

import bpy


EASING = {
    "linear": ("LINEAR", "AUTO"),
    "hold": ("CONSTANT", "AUTO"),
    "ease_in": ("SINE", "EASE_IN"),
    "ease_out": ("SINE", "EASE_OUT"),
    "ease_in_out": ("SINE", "EASE_IN_OUT"),
    "back_out": ("BACK", "EASE_OUT"),
}


def create_material(name, image):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Linear"
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")
    links = material.node_tree.links
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(texture.outputs["Alpha"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    return material


def create_sprite(scene, part, canvas_w, canvas_h, order, cover=False):
    image = bpy.data.images.load(part["asset"], check_existing=True)
    if not image.size[0] or not image.size[1]:
        raise ValueError("Empty puppet image: " + part["asset"])
    ratio = image.size[1] / image.size[0]
    width = canvas_w * part["width"]
    height = width * ratio
    if cover and height < canvas_h:
        height = canvas_h
        width = height / ratio
    px, py = part["pivot"]
    vertices = [
        (-px * width, -(1 - py) * height, 0),
        ((1 - px) * width, -(1 - py) * height, 0),
        ((1 - px) * width, py * height, 0),
        (-px * width, py * height, 0),
    ]
    mesh = bpy.data.meshes.new(part["id"] + "_mesh")
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, coords in zip(mesh.polygons[0].loop_indices,
                            ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop].uv = coords
    mesh.materials.append(create_material(part["id"] + "_material", image))
    sprite = bpy.data.objects.new(part["id"] + "_sprite", mesh)
    scene.collection.objects.link(sprite)
    pivot = bpy.data.objects.new(part["id"] + "_joint", None)
    scene.collection.objects.link(pivot)
    sprite.parent = pivot
    # Depth is attached to the sprite, not the parent joint: nesting never
    # accidentally changes the declared draw order.
    sprite.location.z = part["z"] * 0.02 + order * 0.0001
    return pivot


def get_fcurves(obj):
    """Read action F-curves on Blender 3.6/4.x and layered Actions in 5.x."""
    action = obj.animation_data.action if obj.animation_data else None
    if action is None:
        return []
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    slot = obj.animation_data.action_slot
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            if hasattr(strip, "channelbag"):
                bag = strip.channelbag(slot)
                if bag:
                    curves.extend(bag.fcurves)
    return curves


def animate_joint(pivot, part, rest, canvas_w, canvas_h, frames):
    values = {"dx": 0.0, "dy": 0.0, "rotation_deg": 0.0, "scale": 1.0}
    easing_by_frame = {}

    def key_pose(frame):
        pivot.location = (
            rest[0] + values["dx"] * canvas_w,
            rest[1] - values["dy"] * canvas_h,
            0,
        )
        pivot.rotation_euler = (0, 0, math.radians(values["rotation_deg"]))
        pivot.scale = (values["scale"], values["scale"], 1)
        for prop in ("location", "rotation_euler", "scale"):
            pivot.keyframe_insert(data_path=prop, frame=frame)

    keyframes = part.get("keyframes", [])
    if not keyframes:
        pivot.location = (rest[0], rest[1], 0)
        return
    # Always establish a bind pose at frame 1. User t=0 may override it.
    if keyframes[0]["t"] > 0:
        key_pose(1)
    for kf in keyframes:
        for name in values:
            if kf.get(name) is not None:
                values[name] = kf[name]
        frame = 1 + round(kf["t"] * (frames - 1))
        key_pose(frame)
        easing_by_frame[frame] = kf.get("easing", "ease_in_out")

    # Easing on a keyframe specifies how we ARRIVE at it. Apply that easing
    # to the preceding segment, consistently across location/rotation/scale.
    for curve in get_fcurves(pivot):
        points = sorted(curve.keyframe_points, key=lambda p: p.co.x)
        for previous, following in zip(points, points[1:]):
            name = easing_by_frame.get(round(following.co.x), "ease_in_out")
            interpolation, easing = EASING[name]
            previous.interpolation = interpolation
            if interpolation in ("SINE", "BACK"):
                previous.easing = easing


def main():
    if "--" not in sys.argv:
        raise SystemExit("Usage: blender -b --python SCRIPT -- SPEC FRAME_DIR")
    args = sys.argv[sys.argv.index("--") + 1:]
    if len(args) != 2:
        raise SystemExit("Expected SPEC and FRAME_DIR")
    spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    if spec.get("version") != 2:
        raise ValueError("Only hierarchical puppet rig version 2 is supported")
    frame_dir = Path(args[1]).resolve()
    width, height = int(spec["width"]), int(spec["height"])
    fps, frames = int(spec["fps"]), int(spec["frames"])
    if min(width, height, fps, frames) <= 0:
        raise ValueError("Invalid render dimensions, FPS or frames")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 2
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = frames
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Puppet World")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.02, 0.03, 0.06, 1)

    # Blender ortho_scale is the vertical view size. Correct for 9:16.
    canvas_h = 2.0
    canvas_w = canvas_h * width / height
    bpy.ops.object.camera_add(location=(0, 0, 10))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = canvas_h
    scene.camera = camera

    bg = {"id": "approved_background", "asset": spec["background"],
          "width": 1.0, "pivot": [0.5, 0.5], "z": -100}
    bg_joint = create_sprite(scene, bg, canvas_w, canvas_h, 0, cover=True)
    bg_joint.location = (0, 0, 0)

    parts = spec["parts"]
    pivots = {}
    bind = {}
    # Create all anchors first, so JSON order need not be topological.
    for order, part in enumerate(parts, start=1):
        pivots[part["id"]] = create_sprite(scene, part, canvas_w, canvas_h, order)
        bind[part["id"]] = (
            (part["x"] - 0.5) * canvas_w,
            (0.5 - part["y"]) * canvas_h,
        )
    for part in parts:
        parent = part.get("parent")
        if parent:
            pivots[part["id"]].parent = pivots[parent]
        own = bind[part["id"]]
        ancestor = bind[parent] if parent else (0, 0)
        # Bind position in parent-local coordinates. Rotating a parent moves
        # every child and the sprite attached to that child automatically.
        rest = (own[0] - ancestor[0], own[1] - ancestor[1])
        animate_joint(pivots[part["id"]], part, rest, canvas_w, canvas_h, frames)

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    frame_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(frame_dir / "frame_")
    scene.render.use_file_extension = True
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
