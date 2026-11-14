"""Run ONLY under Blender: blender -b --python blender_cutout_scene.py -- SPEC OUTPUT.

The wrapper validates the JSON and asset paths. This script deliberately does
not eval expressions or execute user-provided Python.
"""
import json
import math
import sys
from pathlib import Path

import bpy


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


def create_layer(scene, layer, canvas_w, canvas_h, frames, order):
    image = bpy.data.images.load(layer["asset"], check_existing=True)
    if not image.size[0] or not image.size[1]:
        raise ValueError("Empty image: " + layer["asset"])
    ratio = image.size[1] / image.size[0]
    width = canvas_w * layer["width"]
    height = width * ratio
    if layer.get("fit") == "cover" and height < canvas_h:
        height = canvas_h
        width = height / ratio

    px, py = layer["pivot"]  # Fractions from top-left of original image
    vertices = [
        (-px * width, -(1 - py) * height, 0),
        ((1 - px) * width, -(1 - py) * height, 0),
        ((1 - px) * width, py * height, 0),
        (-px * width, py * height, 0),
    ]
    mesh = bpy.data.meshes.new(layer["id"] + "_mesh")
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, coords in zip(mesh.polygons[0].loop_indices,
                            ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop].uv = coords
    mesh.materials.append(create_material(layer["id"] + "_material", image))
    plane = bpy.data.objects.new(layer["id"] + "_image", mesh)
    scene.collection.objects.link(plane)

    anchor = bpy.data.objects.new(layer["id"] + "_pivot", None)
    scene.collection.objects.link(anchor)
    plane.parent = anchor
    # Larger Z is closer to the orthographic camera; preserve declared layer order.
    z = layer["z"] * 0.02 + order * 0.0001
    values = {"x": layer["x"], "y": layer["y"], "rotation_deg": 0.0, "scale": 1.0}

    def set_transform(frame):
        anchor.location = ((values["x"] - 0.5) * canvas_w,
                           (0.5 - values["y"]) * canvas_h, z)
        anchor.rotation_euler = (0, 0, math.radians(values["rotation_deg"]))
        anchor.scale = (values["scale"], values["scale"], 1)
        for prop in ("location", "rotation_euler", "scale"):
            anchor.keyframe_insert(data_path=prop, frame=frame)

    keyframes = layer.get("keyframes", [])
    if not keyframes or keyframes[0]["t"] > 0:
        set_transform(1)
    for keyframe in keyframes:
        for key in ("x", "y", "rotation_deg", "scale"):
            if key in keyframe and keyframe[key] is not None:
                values[key] = keyframe[key]
        frame = 1 + round(keyframe["t"] * (frames - 1))
        set_transform(frame)


def main():
    if "--" not in sys.argv:
        raise SystemExit("Usage: blender -b --python SCRIPT -- SPEC OUTPUT")
    args = sys.argv[sys.argv.index("--") + 1:]
    if len(args) != 2:
        raise SystemExit("Expected SPEC and OUTPUT arguments")
    spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    output = Path(args[1]).resolve()
    width, height = int(spec["width"]), int(spec["height"])
    fps, frames = int(spec["fps"]), int(spec["frames"])
    if min(width, height, fps, frames) <= 0:
        raise ValueError("Invalid render size, FPS or frame count")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    # Cycles emission materials work headlessly on CPU, including cloud jobs
    # without GPU/OpenGL. This is a reliability-first MVP, not a speed benchmark.
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
        scene.world = bpy.data.worlds.new("Cutout World")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.02, 0.03, 0.06, 1)

    canvas_w = 2.0
    canvas_h = canvas_w * height / width
    bpy.ops.object.camera_add(location=(0, 0, 10))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = canvas_w
    scene.camera = camera
    for order, layer in enumerate(spec["layers"]):
        create_layer(scene, layer, canvas_w, canvas_h, frames, order)

    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(output)
    scene.render.use_file_extension = False
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
