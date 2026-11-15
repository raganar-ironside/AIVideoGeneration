from puppet_motion_demo import motion_rig


def test_both_motion_modes_have_valid_hierarchical_rigs():
    from historyforgeai.infrastructure.rendering.blender_2d import PuppetRig
    for mode in ("string-puppet", "hinged-cutout"):
        rig = PuppetRig.model_validate(motion_rig(mode))
        assert len(rig.parts) == 12
        assert any(part.id == "torso" and len(part.keyframes) > 2 for part in rig.parts)


def test_motion_modes_differ():
    a = motion_rig("string-puppet")
    b = motion_rig("hinged-cutout")
    assert a != b
