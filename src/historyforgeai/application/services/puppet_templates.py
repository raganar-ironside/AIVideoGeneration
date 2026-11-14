"""Reusable hierarchical 12-part puppet template for manually separated PNGs.

Coordinates are initial joint positions in the 9:16 canvas. They are only
starting estimates: align the pivots/parts to the actual illustration before
approving a scene. This is NOT automatic joint detection or image separation.
"""
PUPPET_PARTS = (
    "torso", "head", "upper_arm_l", "forearm_l", "upper_arm_r", "forearm_r",
    "pelvis", "thigh_l", "shin_l", "thigh_r", "shin_r", "weapon",
)

# id -> (parent, x, y, width, pivot_x, pivot_y, draw_order)
BIND_TEMPLATE = {
    "torso":       (None,          .50, .53, .35, .50, .35, 3),
    "head":        ("torso",       .50, .36, .20, .50, .78, 6),
    "upper_arm_l": ("torso",       .38, .47, .16, .65, .10, 2),
    "forearm_l":   ("upper_arm_l", .32, .59, .13, .50, .10, 2),
    "upper_arm_r": ("torso",       .62, .47, .16, .35, .10, 5),
    "forearm_r":   ("upper_arm_r", .68, .59, .13, .50, .10, 5),
    "pelvis":      ("torso",       .50, .67, .30, .50, .10, 3),
    "thigh_l":     ("pelvis",      .44, .72, .16, .50, .10, 2),
    "shin_l":      ("thigh_l",     .43, .85, .14, .50, .10, 2),
    "thigh_r":     ("pelvis",      .56, .72, .16, .50, .10, 4),
    "shin_r":      ("thigh_r",     .57, .85, .14, .50, .10, 4),
    "weapon":      ("forearm_r",   .73, .68, .13, .25, .85, 7),
}


def puppet_template(scene_index: int) -> dict:
    root = f"animation/assets/scene_{scene_index:02d}"
    parts = []
    for name in PUPPET_PARTS:
        parent, x, y, width, px, py, z = BIND_TEMPLATE[name]
        keyframes = []
        if name == "torso":
            keyframes = [
                {"t": 0, "rotation_deg": 0, "easing": "linear"},
                {"t": .55, "rotation_deg": -5, "easing": "ease_in_out"},
                {"t": 1, "rotation_deg": -2, "easing": "ease_out"},
            ]
        elif name == "upper_arm_r":
            keyframes = [
                {"t": 0, "rotation_deg": 0, "easing": "linear"},
                {"t": .55, "rotation_deg": 65, "easing": "back_out"},
                {"t": 1, "rotation_deg": 65, "easing": "hold"},
            ]
        elif name == "forearm_r":
            keyframes = [
                {"t": 0, "rotation_deg": 0, "easing": "linear"},
                {"t": .55, "rotation_deg": -30, "easing": "ease_out"},
                {"t": 1, "rotation_deg": -30, "easing": "hold"},
            ]
        elif name == "head":
            keyframes = [
                {"t": 0, "rotation_deg": 0, "easing": "linear"},
                {"t": .4, "rotation_deg": 8, "easing": "ease_in_out"},
                {"t": 1, "rotation_deg": 8, "easing": "hold"},
            ]
        parts.append({
            "id": name, "asset": f"{root}/{name}.png",
            "parent": parent, "x": x, "y": y, "width": width,
            "pivot": [px, py], "z": z, "keyframes": keyframes,
        })
    return {"version": 2, "parts": parts}
