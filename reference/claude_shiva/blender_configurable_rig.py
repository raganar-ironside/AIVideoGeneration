"""Reusable Blender 2D rig renderer built from Claude's coordinate/pivot approach.

Invoke: blender -b --python blender_configurable_rig.py -- SCENE_JSON OUTPUT_DIR
The source art manifest is Claude's original parts.json (canvas coordinates).
"""
import json
import math
import sys
from pathlib import Path

import bpy


def material(path, name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(path), check_existing=True)
    texture.interpolation = "Linear"
    emission = nodes.new("ShaderNodeEmission")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")
    links = m.node_tree.links
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(texture.outputs["Alpha"], mix.inputs["Fac"])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    return m


def quad(scene, name, bounds, z, image_path):
    x0, y0, x1, y1 = bounds
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(x0, y0, 0), (x1, y0, 0),
                      (x1, y1, 0), (x0, y1, 0)], [], [(0, 1, 2, 3)])
    mesh.update()
    uv = mesh.uv_layers.new(name="UV")
    for loop, coord in zip(mesh.polygons[0].loop_indices,
                           ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop].uv = coord
    mesh.materials.append(material(image_path, name + "_mat"))
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.location.z = z
    return obj


def empty(scene, name, parent=None, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = location
    return obj


def keyframes(obj, channel, points, fps, frame_count):
    if channel == "rotation_deg":
        prop, index, converter = "rotation_euler", 2, math.radians
    elif channel == "x":
        prop, index, converter = "location", 0, float
    elif channel == "y":
        prop, index, converter = "location", 1, float
    else:
        raise ValueError("Unknown animation channel: " + channel)
    previous = -1
    for time, value in points:
        frame = min(frame_count, 1 + round(float(time) * fps))
        if frame <= previous:
            raise ValueError("Keyframe times must be strictly increasing")
        previous = frame
        getattr(obj, prop)[index] = converter(value)
        obj.keyframe_insert(data_path=prop, index=index, frame=frame)


def render(spec, output_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    fps = int(spec.get("fps", 24))
    duration = float(spec.get("duration", 2))
    frames = round(fps * duration)
    if fps < 1 or duration <= 0 or frames < 2:
        raise ValueError("Invalid FPS or duration")
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = int(spec.get("samples", 6))
    scene.render.resolution_x = int(spec.get("width", 720))
    scene.render.resolution_y = int(spec.get("height", 1280))
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = frames
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output_dir / "f_")

    camera = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = float(spec.get("ortho_scale", 19.2))
    camera.location = (0, 0, 20)
    scene.camera = camera

    assets = Path(spec["assets_dir"]).resolve()
    manifest = json.loads((assets / "parts.json").read_text(encoding="utf-8"))
    canvas = spec["canvas"]
    cw, ch = int(canvas["width"]), int(canvas["height"])
    unit = float(spec.get("pixel_scale", 0.0072))
    def offset(a, b):
        return ((a[0] - b[0]) * unit, -(a[1] - b[1]) * unit, 0)

    for layer in spec.get("backgrounds", []):
        name = layer["asset"]
        quad(scene, "bg_" + name,
             layer.get("bounds", [-5.4, -9.6, 5.4, 9.6]),
             float(layer["z"]), assets / (name + ".png"))

    # Rig hierarchy defined entirely by the JSON scene.
    rig = spec["rig"]
    pivots = rig["pivots"]
    root_name = rig["root"]
    joints = {}
    def make_joint(name):
        if name in joints:
            return joints[name]
        info = pivots[name]
        parent_name = info.get("parent")
        parent = make_joint(parent_name) if parent_name else None
        location = offset(info["xy"], pivots[parent_name]["xy"]) if parent_name else tuple(info.get("location", [0, 0, 0]))
        joints[name] = empty(scene, "joint_" + name, parent, location)
        return joints[name]

    for name in pivots:
        make_joint(name)
    for name, info in manifest.items():
        parent_name = info["parent"]
        if parent_name not in joints:
            raise ValueError("Missing joint " + parent_name + " for " + name)
        x0, y0, x1, y1 = info["bbox"]
        pivot = info["pivot"]
        # Crop placement is relative to the sprite's own canvas pivot.
        x0u, y0u, _ = offset((x0, y0), pivot)
        x1u, y1u, _ = offset((x1, y1), pivot)
        obj = quad(scene, "part_" + name, (x0u, y1u, x1u, y0u),
                   float(info["z"]), assets / (name + ".png"))
        obj.parent = joints[parent_name]
        obj.location.x, obj.location.y, _ = offset(pivot, pivots[parent_name]["xy"])

    objects = dict(joints)
    for layer in spec.get("overlays", []):
        name = layer["asset"]
        obj = quad(scene, "overlay_" + name, layer["bounds"],
                   float(layer["z"]), assets / (name + ".png"))
        obj.location = layer.get("location", [0, 0, 0])
        objects[layer["id"]] = obj

    for name, channels in spec.get("animation", {}).items():
        if name not in objects:
            raise ValueError("Animation references unknown object: " + name)
        for channel, points in channels.items():
            keyframes(objects[name], channel, points, fps, frames)
    output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(animation=True)


def main():
    if "--" not in sys.argv:
        raise SystemExit("Usage: blender -b --python SCRIPT -- SCENE_JSON OUTPUT_DIR")
    args = sys.argv[sys.argv.index("--") + 1:]
    if len(args) != 2:
        raise SystemExit("Expected SCENE_JSON OUTPUT_DIR")
    scene_path = Path(args[0]).resolve()
    spec = json.loads(scene_path.read_text(encoding="utf-8"))
    render(spec, Path(args[1]).resolve())


if __name__ == "__main__":
    main()
