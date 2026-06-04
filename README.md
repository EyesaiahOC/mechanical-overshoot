# Mechanical Overshoot

A Blender add-on that adds mechanical elastic overshoot to animated F-curves. Select a keyframe, click Apply — the add-on attaches an additive SINC Function Generator modifier to the F-curve that creates a damped oscillation settle or departure kick, using only four controls.

## How It Works

The add-on adds a native **Function Generator (SINC)** F-curve modifier set to additive mode. The modifier is restricted to a frame range starting at (or ending at) the selected keyframe. The phase multiplier is set so the SINC function evaluates to exactly zero at both the anchor frame and the far end of the range — no blend hacks, mathematically guaranteed settle.

Direction is auto-detected from the adjacent keyframe slope, so the first oscillation always overshoots in the correct direction relative to the motion.

## Install

1. **Edit → Preferences → Add-ons → Install**
2. Select the `mechanical_overshoot` folder (or zip it first)
3. Enable **Mechanical Overshoot**

For fast iteration during development, install as a package. The `__init__.py` reloads `mechanical_overshoot.py` on **Reload Scripts** so you don't need to reinstall on every change.

## Use

1. Open the **Graph Editor**
2. Select one or more keyframes
3. Press `N` → **Mechanical** tab
4. Set your parameters
5. Click **Apply Mechanical Overshoot**

Adjust **Amplitude** and **Bounces** live with the sliders — the modifier updates in place. **Duration** and **Direction** require re-applying.

To remove the effect, select the keyframe and click **Remove Mechanical Overshoot**.

## Parameters

| Parameter | Description |
|---|---|
| **Direction** | **After** — arrival settle, oscillation after the anchor keyframe. **Before** — departure kick, oscillation before the anchor keyframe. |
| **Duration** | Total frames the effect lasts. |
| **Amplitude** | Peak overshoot size in curve value units (degrees, metres, etc.). |
| **Bounces** | Number of oscillation lobes. 1 = single overshoot and settle. Higher values give a looser, more elastic feel. |

## Notes

- The modifier is **additive** and **non-destructive** — your original keyframes are untouched.
- The SINC zeros are mathematically exact at both ends of the restricted range, so the curve settles precisely at the keyframe value with no residual offset.
- Live update works for **Amplitude** and **Bounces**. For **Duration** or **Direction** changes, delete the modifier (Remove button) and re-apply.
- When multiple keyframes are selected, Apply and Remove operate on all of them simultaneously.
