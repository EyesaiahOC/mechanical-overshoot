bl_info = {
    "name": "Mechanical Overshoot",
    "author": "Isaac O'Connor",
    "version": (0, 3, 0),
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
_last_sync_key = None

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



def _decode_modifier(modifier, anchor_frame, fcurve=None, anchor_kp=None):
    """Reverse _configure_modifier to recover user-facing params."""
    after = modifier.phase_multiplier >= 0
    if after:
        duration = max(2, round(modifier.frame_end - anchor_frame))
    else:
        duration = max(2, round(anchor_frame - modifier.frame_start))
    bounces = max(1, round(abs(modifier.phase_multiplier) * duration))
    amplitude = abs(modifier.amplitude) / _NORMALIZER
    flip = False
    if fcurve is not None and anchor_kp is not None:
        dir_sign = _direction_sign(fcurve, anchor_kp, after)
        # Without flip: amplitude = -dir_sign * ..., so amplitude * dir_sign < 0.
        # With flip the sign is negated, so amplitude * dir_sign > 0.
        flip = (modifier.amplitude * dir_sign > 0)
    return {
        'direction': 'AFTER' if after else 'BEFORE',
        'duration': duration,
        'amplitude': amplitude,
        'bounces': bounces,
        'flip': flip,
    }


def _configure_modifier(modifier, anchor_frame, duration, amplitude, bounces, dir_sign, after, flip=False):
    """
    phase_multiplier = ±bounces/duration so SINC evaluates to exactly zero at
    both the anchor frame (x=1) and the far end of the restricted range (x=1+bounces).
    No blend_in/out needed — zeros are mathematically exact.
    """
    pm = bounces / duration if after else -(bounces / duration)
    po = 1.0 - pm * anchor_frame

    effective_sign = dir_sign * (-1 if flip else 1)
    modifier.function_type = 'SINC'
    modifier.use_additive = True
    modifier.amplitude = -effective_sign * _NORMALIZER * amplitude
    modifier.phase_multiplier = pm
    modifier.phase_offset = po
    modifier.value_offset = 0.0

    modifier.use_restricted_range = True
    modifier.frame_start = anchor_frame if after else anchor_frame - duration
    modifier.frame_end = (anchor_frame + duration) if after else anchor_frame
    modifier.blend_in = 0.0
    modifier.blend_out = 0.0


def _apply(fcurve, anchor_kp, duration, amplitude, bounces, after, flip=False):
    anchor_frame = anchor_kp.co.x
    dir_sign = _direction_sign(fcurve, anchor_kp, after)

    modifier = _find_modifier(fcurve, anchor_frame)
    if modifier is None:
        modifier = fcurve.modifiers.new(type='FNGENERATOR')
    modifier.name = _modifier_name(anchor_frame)

    _configure_modifier(modifier, anchor_frame, duration, amplitude, bounces, dir_sign, after, flip)
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
            _configure_modifier(modifier, anchor_kp.co.x, self.duration, self.amplitude, self.bounces, dir_sign, after, self.flip)
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


def _sync_timer():
    global _last_sync_key, _IS_UPDATING
    if _IS_UPDATING:
        return 0.1

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'GRAPH_EDITOR':
                continue
            for region in area.regions:
                if region.type != 'WINDOW':
                    continue
                with bpy.context.temp_override(window=window, area=area, region=region):
                    scene = bpy.context.scene
                    if not scene or not hasattr(scene, 'mechanical_overshoot_settings'):
                        return 0.1

                    first_fc = first_kp = first_mod = None
                    for fc, kp in _selected_keyframes(bpy.context):
                        mod = _find_modifier(fc, kp.co.x)
                        if mod is not None:
                            first_fc, first_kp, first_mod = fc, kp, mod
                            break

                    if first_kp is None:
                        _last_sync_key = None
                        return 0.1

                    try:
                        sync_key = (first_fc.id_data.name, first_fc.data_path,
                                    first_fc.array_index, round(first_kp.co.x, 4))
                    except Exception:
                        sync_key = (id(first_fc), round(first_kp.co.x, 4))

                    if sync_key == _last_sync_key:
                        return 0.1
                    _last_sync_key = sync_key

                    params = _decode_modifier(first_mod, first_kp.co.x, first_fc, first_kp)
                    s = scene.mechanical_overshoot_settings
                    _IS_UPDATING = True
                    try:
                        if s.direction != params['direction']:
                            s.direction = params['direction']
                        if s.duration != params['duration']:
                            s.duration = params['duration']
                        if abs(s.amplitude - params['amplitude']) > 0.005:
                            s.amplitude = params['amplitude']
                        if s.bounces != params['bounces']:
                            s.bounces = params['bounces']
                        if s.flip != params['flip']:
                            s.flip = params['flip']
                    finally:
                        _IS_UPDATING = False
                return 0.1
    return 0.1


class MechanicalOvershootSettings(PropertyGroup):
    direction: EnumProperty(
        name="Direction",
        items=(
            ('AFTER', "After", "Arrival settle — additive oscillation after the anchor keyframe"),
            ('BEFORE', "Before", "Departure kick — additive oscillation before the anchor keyframe"),
        ),
        default='AFTER',
        update=_live_update,
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
    flip: bpy.props.BoolProperty(
        name="Flip Direction",
        description="Invert the overshoot — wave goes opposite to the natural motion direction",
        default=False,
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
            _apply(fcurve, anchor_kp, s.duration, s.amplitude, s.bounces, after, s.flip)
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
        layout.prop(s, "flip")


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
    if not bpy.app.timers.is_registered(_sync_timer):
        bpy.app.timers.register(_sync_timer, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_sync_timer):
        bpy.app.timers.unregister(_sync_timer)
    del bpy.types.Scene.mechanical_overshoot_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
