bl_info = {
    "name": "Mechanical Overshoot",
    "author": "Isaac O'Connor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "Graph Editor > Sidebar > Mechanical",
    "description": "Add elastic overshoot to mechanical animation keyframes.",
    "category": "Animation",
}

import bpy
import math
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty
from bpy.types import Operator, Panel, PropertyGroup

MODIFIER_PREFIX = "MechOvershoot"
_IS_UPDATING = False

# SINC first lobe peaks at x=1.5 with magnitude 1/(1.5π) ≈ 0.2122.
# Normalise so user's Amplitude directly equals peak overshoot in curve units.
_NORMALIZER = 1.5 * math.pi  # ≈ 4.712


def _selected_keyframes(context):
    seen = set()
    for fcurve in (getattr(context, 'editable_fcurves', None) or []):
        for kp in fcurve.keyframe_points:
            if kp.select_control_point:
                uid = (id(fcurve), round(kp.co.x, 4))
                if uid not in seen:
                    seen.add(uid)
                    yield fcurve, kp


def _prev_keyframe(fcurve, frame):
    result = None
    for kp in fcurve.keyframe_points:
        if kp.co.x < frame - 0.001:
            if result is None or kp.co.x > result.co.x:
                result = kp
    return result


def _next_keyframe(fcurve, frame):
    result = None
    for kp in fcurve.keyframe_points:
        if kp.co.x > frame + 0.001:
            if result is None or kp.co.x < result.co.x:
                result = kp
    return result


def _direction_sign(fcurve, anchor_kp, after):
    """
    +1 if the curve arrives from below (After) or departs upward (Before).
    The amplitude formula uses this to flip the SINC so the first oscillation
    goes in the correct direction relative to the motion.
    """
    v = anchor_kp.co.y
    if after:
        ref = _prev_keyframe(fcurve, anchor_kp.co.x)
        return 1 if (ref is None or ref.co.y <= v) else -1
    else:
        ref = _next_keyframe(fcurve, anchor_kp.co.x)
        return -1 if (ref is None or ref.co.y >= v) else 1


def _modifier_name(anchor_frame):
    return f"{MODIFIER_PREFIX} {int(round(anchor_frame))}"


def _find_modifier(fcurve, anchor_frame):
    name = _modifier_name(anchor_frame)
    for m in fcurve.modifiers:
        if m.name == name:
            return m
    return None


def _configure_modifier(modifier, anchor_frame, duration, amplitude, bounces, dir_sign, after):
    """
    phase_multiplier = ±bounces/duration so SINC evaluates to exactly zero at
    both the anchor frame (x=1) and the far end of the restricted range (x=1+bounces).
    No blend_in/out needed — zeros are mathematically exact.
    """
    pm = bounces / duration if after else -(bounces / duration)
    po = 1.0 - pm * anchor_frame

    modifier.function_type = 'SINC'
    modifier.use_additive = True
    modifier.amplitude = -dir_sign * _NORMALIZER * amplitude
    modifier.phase_multiplier = pm
    modifier.phase_offset = po
    modifier.value_offset = 0.0

    modifier.use_restricted_range = True
    modifier.frame_start = anchor_frame if after else anchor_frame - duration
    modifier.frame_end = (anchor_frame + duration) if after else anchor_frame
    modifier.blend_in = 0.0
    modifier.blend_out = 0.0


def _apply(fcurve, anchor_kp, duration, amplitude, bounces, after):
    anchor_frame = anchor_kp.co.x
    anchor_value = anchor_kp.co.y
    dir_sign = _direction_sign(fcurve, anchor_kp, after)

    modifier = _find_modifier(fcurve, anchor_frame)
    if modifier is None:
        modifier = fcurve.modifiers.new(type='FNGENERATOR')
    modifier.name = _modifier_name(anchor_frame)

    _configure_modifier(modifier, anchor_frame, duration, amplitude, bounces, dir_sign, after)
    fcurve.update()


def _live_update(self, context):
    global _IS_UPDATING
    if _IS_UPDATING:
        return
    _IS_UPDATING = True
    try:
        after = self.direction == 'AFTER'
        changed = False
        for fcurve, anchor_kp in _selected_keyframes(context):
            modifier = _find_modifier(fcurve, anchor_kp.co.x)
            if modifier is None:
                continue
            dir_sign = _direction_sign(fcurve, anchor_kp, after)
            _configure_modifier(modifier, anchor_kp.co.x, self.duration, self.amplitude, self.bounces, dir_sign, after)
            fcurve.update()
            changed = True
        if changed:
            screen = getattr(context, 'screen', None)
            if screen:
                for area in screen.areas:
                    if area.type == 'GRAPH_EDITOR':
                        area.tag_redraw()
    finally:
        _IS_UPDATING = False


class MechanicalOvershootSettings(PropertyGroup):
    direction: EnumProperty(
        name="Direction",
        items=(
            ('AFTER', "After", "Arrival settle — additive oscillation after the anchor keyframe"),
            ('BEFORE', "Before", "Departure kick — additive oscillation before the anchor keyframe"),
        ),
        default='AFTER',
    )
    duration: IntProperty(
        name="Duration",
        description="Total frames for the overshoot effect",
        default=10,
        min=2,
        max=500,
        update=_live_update,
    )
    amplitude: FloatProperty(
        name="Amplitude",
        description="Peak overshoot in curve value units",
        default=5.0,
        soft_min=0.0,
        soft_max=180.0,
        precision=2,
        update=_live_update,
    )
    bounces: IntProperty(
        name="Bounces",
        description="Oscillation lobes — 1 is a single overshoot, higher values add more elastic bounce",
        default=1,
        min=1,
        max=10,
        update=_live_update,
    )


class GRAPH_OT_remove_mechanical_overshoot(Operator):
    bl_idname = "graph.remove_mechanical_overshoot"
    bl_label = "Remove Mechanical Overshoot"
    bl_description = "Remove MechOvershoot modifier from each selected keyframe's F-curve"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'GRAPH_EDITOR'

    def execute(self, context):
        removed = 0
        for fcurve, anchor_kp in _selected_keyframes(context):
            modifier = _find_modifier(fcurve, anchor_kp.co.x)
            if modifier:
                fcurve.modifiers.remove(modifier)
                fcurve.update()
                removed += 1

        if removed:
            self.report({'INFO'}, f"Removed from {removed} keyframe(s).")
            return {'FINISHED'}

        self.report({'WARNING'}, "No MechOvershoot modifiers found on selected keyframes.")
        return {'CANCELLED'}


class GRAPH_OT_apply_mechanical_overshoot(Operator):
    bl_idname = "graph.apply_mechanical_overshoot"
    bl_label = "Apply Mechanical Overshoot"
    bl_description = "Add SINC overshoot modifier to each selected keyframe's F-curve"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'GRAPH_EDITOR'

    def execute(self, context):
        s = context.scene.mechanical_overshoot_settings
        after = s.direction == 'AFTER'
        applied = 0

        for fcurve, anchor_kp in _selected_keyframes(context):
            _apply(fcurve, anchor_kp, s.duration, s.amplitude, s.bounces, after)
            applied += 1

        if applied:
            self.report({'INFO'}, f"Applied to {applied} keyframe(s).")
            return {'FINISHED'}

        self.report({'WARNING'}, "No keyframes selected.")
        return {'CANCELLED'}


class GRAPH_PT_mechanical_overshoot(Panel):
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_category = "Mechanical"
    bl_label = "Mechanical Overshoot"

    def draw(self, context):
        layout = self.layout
        s = context.scene.mechanical_overshoot_settings
        layout.operator("graph.apply_mechanical_overshoot", icon="MOD_WAVE")
        layout.operator("graph.remove_mechanical_overshoot", icon="X")
        layout.separator()
        layout.prop(s, "direction", expand=True)
        layout.prop(s, "duration")
        layout.prop(s, "amplitude")
        layout.prop(s, "bounces")


classes = (
    MechanicalOvershootSettings,
    GRAPH_OT_remove_mechanical_overshoot,
    GRAPH_OT_apply_mechanical_overshoot,
    GRAPH_PT_mechanical_overshoot,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mechanical_overshoot_settings = PointerProperty(type=MechanicalOvershootSettings)


def unregister():
    del bpy.types.Scene.mechanical_overshoot_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
