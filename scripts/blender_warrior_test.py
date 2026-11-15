"""Procedural Maratha-inspired 2.5D warrior: no PNG inputs or Pillow needed.

Run:
  blender -b --python scripts/blender_warrior_test.py -- --output workspace/blender_warrior --preview
  blender -b --python scripts/blender_warrior_test.py -- --output workspace/blender_warrior --animate
"""
import argparse
import math
import sys
from pathlib import Path

import bpy

PALETTE = {
    "skin": (0.55, 0.29, 0.18, 1), "skin_light": (0.80, 0.51, 0.31, 1),
    "cloth": (0.82, 0.70, 0.49, 1), "cloth_shadow": (0.52, 0.40, 0.28, 1),
    "saffron": (0.76, 0.20, 0.055, 1), "saffron_light": (0.98, 0.43, 0.12, 1),
    "gold": (0.90, 0.66, 0.22, 1), "metal": (0.55, 0.64, 0.67, 1),
    "metal_dark": (0.18, 0.25, 0.30, 1), "hair": (0.12, 0.085, 0.065, 1),
    "boot": (0.21, 0.13, 0.085, 1), "background": (0.12, 0.17, 0.19, 1),
}
MAT = {}


def material(name):
    if name not in MAT:
        m = bpy.data.materials.new(name)
        m.diffuse_color = PALETTE[name]
        m.use_nodes = True
        nodes = m.node_tree.nodes
        nodes.clear()
        e = nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = PALETTE[name]
        o = nodes.new("ShaderNodeOutputMaterial")
        m.node_tree.links.new(e.outputs[0], o.inputs["Surface"])
        MAT[name] = m
    return MAT[name]


def polygon(name, vertices, color, depth, parent=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(x, y, 0) for x, y in vertices], [], [tuple(range(len(vertices)))])
    mesh.update()
    mesh.materials.append(material(color))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location.z = depth
    if parent is not None:
        obj.parent = parent
    return obj


def ellipse(name, x, y, rx, ry, color, depth, parent=None, count=40):
    pts = [(x + rx * math.cos(i * 2 * math.pi / count),
            y + ry * math.sin(i * 2 * math.pi / count)) for i in range(count)]
    return polygon(name, pts, color, depth, parent)


def joint(name, x, y, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.location = (x, y, 0)
    return obj


def limb(name, length, width, color, parent, depth):
    # Joint is at (0,0); limb points down the local Y axis.
    return polygon(name, [(-width, 0), (width, 0),
                          (width * 0.82, -length), (-width * 0.82, -length)],
                   color, depth, parent)


def rotate(obj, keys):
    for frame, angle in keys:
        obj.rotation_euler.z = math.radians(angle)
        obj.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
    if obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action
        if hasattr(action, "fcurves"):
            for fc in action.fcurves:
                for k in fc.keyframe_points:
                    k.interpolation = "BEZIER"


def build_character():
    root = joint("warrior_root", 0, 0)
    # Rear sash, trousers and boots
    polygon("sash_trailing", [(-0.5, 0.8), (-1.25, 0.3), (-1.8, -0.4),
                              (-1.25, -0.25), (-0.4, 0.3)], "saffron", -0.20, root)
    for side in (-1, 1):
        x = side * 0.35
        polygon("trouser_%s" % side, [(x - 0.30, -0.65), (x + 0.30, -0.65),
                (x + 0.23, -2.15), (x - 0.24, -2.15)], "cloth", 0.0, root)
        polygon("boot_%s" % side, [(x - 0.23, -2.08), (x + 0.23, -2.08),
                (x + 0.33, -2.57), (x - 0.31, -2.57)], "boot", 0.06, root)
        polygon("boot_trim_%s" % side, [(x - 0.23, -2.12), (x + 0.23, -2.12),
                (x + 0.25, -2.21), (x - 0.25, -2.21)], "gold", 0.08, root)

    polygon("coat", [(-0.77, 1.18), (0.77, 1.18), (0.62, -0.65),
                      (0.86, -1.20), (-0.87, -1.20), (-0.62, -0.65)],
            "cloth", 0.15, root)
    polygon("coat_center", [(-0.08, 1.1), (0.18, 1.1), (0.04, -1.08),
                             (-0.18, -1.08)], "cloth_shadow", 0.17, root)
    for i in range(5):
        ellipse("coat_button_%d" % i, 0.13, 0.75 - i * 0.35,
                0.055, 0.055, "gold", 0.21, root, 20)
    polygon("belt", [(-0.79, -0.38), (0.75, -0.38),
                      (0.73, -0.65), (-0.79, -0.65)], "saffron", 0.23, root)
    polygon("belt_highlight", [(-0.78, -0.40), (0.74, -0.40),
                                (0.74, -0.46), (-0.78, -0.46)], "gold", 0.24, root)
    polygon("waist_sash", [(0.32, -0.51), (0.75, -0.56), (0.62, -1.65),
                           (0.38, -1.35)], "saffron_light", 0.26, root)

    # Arms use parented pivot objects; a separate sword is parented to the right hand.
    arms = {}
    for side, label in [(-1, "left"), (1, "right")]:
        shoulder = joint(label + "_shoulder", side * 0.71, 1.02, root)
        limb(label + "_upper", 0.93, 0.25, "cloth", shoulder, 0.27)
        ellipse(label + "_shoulder_trim", 0, -0.05, 0.27, 0.16, "gold", 0.30, shoulder)
        elbow = joint(label + "_elbow", 0, -0.88, shoulder)
        limb(label + "_forearm", 0.78, 0.18, "metal_dark", elbow, 0.33)
        polygon(label + "_gauntlet", [(-0.19, -0.18), (0.19, -0.18),
                (0.22, -0.59), (-0.22, -0.59)], "metal", 0.35, elbow)
        hand = joint(label + "_hand_joint", 0, -0.73, elbow)
        ellipse(label + "_hand", 0, -0.07, 0.17, 0.20, "skin", 0.39, hand)
        arms[label] = (shoulder, elbow, hand)

    # Head and turban: hand-built geometry, not an AI asset.
    ellipse("neck", 0, 1.24, 0.23, 0.31, "skin", 0.27, root)
    ellipse("hair_back", 0, 1.86, 0.47, 0.56, "hair", 0.29, root)
    ellipse("face", 0, 1.84, 0.40, 0.51, "skin", 0.32, root)
    polygon("nose", [(0.22, 1.90), (0.45, 1.75), (0.19, 1.72)],
            "skin_light", 0.36, root)
    ellipse("beard", 0.01, 1.53, 0.33, 0.22, "hair", 0.36, root)
    ellipse("eye", 0.19, 1.95, 0.065, 0.045, "hair", 0.38, root, 24)
    polygon("eyebrow", [(0.10, 2.05), (0.30, 2.08),
                         (0.30, 2.02), (0.10, 2.00)], "hair", 0.39, root)
    ellipse("turban_base", 0, 2.33, 0.58, 0.34, "saffron", 0.43, root)
    for i in range(4):
        polygon("turban_fold_%d" % i,
                [(-0.50 + i * 0.23, 2.20), (-0.35 + i * 0.23, 2.57),
                 (-0.25 + i * 0.23, 2.57), (-0.37 + i * 0.23, 2.19)],
                "saffron_light" if i % 2 else "gold", 0.45 + i * 0.001, root)
    ellipse("turban_jewel", 0.30, 2.43, 0.10, 0.12, "gold", 0.50, root, 24)

    right_shoulder, right_elbow, right_hand = arms["right"]
    # Sword blade points along local -Y; hand joint drives the entire weapon.
    polygon("sword_guard", [(-0.33, -0.17), (0.33, -0.17),
                             (0.31, -0.25), (-0.31, -0.25)], "gold", 0.48, right_hand)
    polygon("sword_grip", [(-0.065, -0.15), (0.065, -0.15),
                            (0.06, 0.35), (-0.06, 0.35)], "boot", 0.48, right_hand)
    polygon("sword_blade", [(-0.10, -0.22), (0.10, -0.22),
                             (0.12, -1.95), (0.04, -2.24), (-0.04, -1.96)],
            "metal", 0.47, right_hand)
    polygon("sword_glint", [(-0.03, -0.29), (0.025, -0.29),
                             (0.04, -1.87), (-0.015, -1.90)],
            "skin_light", 0.49, right_hand)

    # Sword raise, with hand and elbow coordinated. Animation is intentionally
    # a rig-mechanics test, not a finished cinematic sword fight.
    rotate(right_shoulder, [(1, -15), (18, -60), (36, -120), (72, -140)])
    rotate(right_elbow, [(1, -10), (18, -35), (36, -10), (72, 8)])
    rotate(right_hand, [(1, 0), (36, 50), (72, 75)])
    rotate(arms["left"][0], [(1, 12), (36, 22), (72, 15)])
    rotate(root, [(1, -1), (36, 1.5), (72, 0)])
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="workspace/blender_warrior")
    parser.add_argument("--preview", action="store_true",
                        help="Render just a single pose PNG")
    parser.add_argument("--animate", action="store_true",
                        help="Render 72 PNG frames for a 3-second animation")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    available = {x.identifier for x in scene.render.bl_rna.properties["engine"].enum_items}
    engine = next((x for x in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE") if x in available), None)
    if not engine:
        raise RuntimeError("EEVEE unavailable; check Blender version")
    scene.render.engine = engine
    scene.render.resolution_x = 360
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 72
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new("WarriorWorld")
    scene.world.color = PALETTE["background"][:3]
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 18)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 8.2
    scene.camera = camera
    build_character()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.animate:
        scene.render.filepath = str(out / "warrior_")
        bpy.ops.render.render(animation=True)
        print("Frames:", out)
    else:
        scene.frame_set(36)
        scene.render.filepath = str(out / "warrior_pose.png")
        bpy.ops.render.render(write_still=True)
        print("Pose:", scene.render.filepath)


if __name__ == "__main__":
    main()
