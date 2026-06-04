# Mechanical Overshoot Prototype

This is a small Blender add-on prototype that automates your manual Graph Editor setup.

It does not add keyframes. It adds or updates one native **Built-In Function / Function Generator** F-Curve modifier per selected keyframe.

## Install

1. In Blender, go to **Edit > Preferences > Add-ons**.
2. Click **Install...**.
3. Choose either `mechanical_overshoot.py` for the single-file add-on, or install this add-on as a package if you want the `__init__.py` reload helper.
4. Enable **Mechanical Overshoot**.

For fast iteration, use the package install. Put `__init__.py` and `mechanical_overshoot.py` inside a package folder named `mechanical_overshoot` or another Python-friendly name without spaces. The package `__init__.py` explicitly reloads `mechanical_overshoot.py`, so Blender's **Reload Scripts** command picks up the latest edited version instead of keeping the cached module.

## Use

1. Open the **Graph Editor**.
2. Select one or more keyframes.
3. Press `N` to open the sidebar.
4. Open the **Mechanical** tab.
5. Click **Apply Mechanical Overshoot**.
6. Keep the same keyframe selected and adjust the controls to update that modifier live.

The add-on creates a Function Generator modifier named like `Mechanical Overshoot 35`, where `35` is the selected keyframe frame.

If you press the button again on the same selected keyframe, it updates that modifier instead of adding another one.

Existing Mechanical Overshoot modifiers on the currently selected keyframes update live while you change the panel controls. The add-on does not create new modifiers until you press **Apply Mechanical Overshoot**.

When exactly one keyframe with an existing Mechanical Overshoot modifier is selected, the panel controls load that modifier's saved settings.

## Current Defaults

- Function type: **Normalized Sine**
- Additive: **On**
- Offshoot Size: `2`
- Time Offset: `0`
- Waves in Range: `0.25`
- Blend In/Out: half of offshoot size
- Scale Mode: **Relative**
- Amplitude: `0.12`
- Amplitude Scale: `1`
- Phase Offset: `2.7`
- Value Offset: `0`
- Restricted Frame Range:
  - selected frame plus time offset to selected frame plus time offset plus offshoot size

In **Relative** scale mode, the add-on looks at the selected keyframe and its local neighboring keyframe movement. It then multiplies that movement by **Amplitude** and **Amplitude Scale**, so a 1 mm location move produces a tiny overshoot and a large movement produces a proportionally larger overshoot. If the preferred neighboring movement is flat, it checks the other adjacent side, then the wider curve span, and finally falls back to zero rather than inventing a large default amplitude.

**Amplitude Scale** is the master size control for the generated overshoot wave. **Amplitude** is the base strength control. In Relative mode, the final native modifier amplitude is:

`local graph movement * Amplitude * Amplitude Scale`

In Absolute mode, the final native modifier amplitude is:

`Amplitude * Amplitude Scale`

**Waves in Range** converts to Blender's native Function Generator phase multiplier based on the current Offshoot Size. Increasing the value fits more wave cycles inside the restricted frame range.

**Time Offset** places the start of the overshoot range relative to the selected keyframe. `0` starts on the selected keyframe, negative values start before it, and positive values start after it. For example, with a selected keyframe on frame `35`, offshoot size `3`, and time offset `-3`, the restricted range is `32-35`; with time offset `3`, the restricted range is `38-41`.

**Value Offset** now writes directly to Blender's native Function Generator value offset. It is no longer scaled automatically.

## Notes

**Flip Direction** currently flips the generated wave internally while keeping the visible amplitude control positive. This is the first prototype version, so the exact peak/trough alignment may need tuning against your manual Blender setup.
