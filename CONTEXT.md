# Mechanical Overshoot — Context & Ubiquitous Language

## What It Does

Blender add-on that applies a mechanical overshoot effect to animated F-curves in the Graph Editor. Animator places clean linear keyframes; the add-on adds a single duplicate keyframe and sets native Blender elastic interpolation to create a damped oscillation settle or departure kick.

## Core Concept

A mechanical object (dial rotating 0°→90°, arm extending, lever locking) does not stop cleanly at its target. It overshoots, bounces back, and settles. This add-on automates the Graph Editor macro that produces that effect using Blender's native elastic easing.

## The Macro (what Apply does)

1. Animator selects a keyframe (the **anchor keyframe**)
2. Add-on duplicates it N frames forward or backward — the **overshoot keyframe**
3. Sets elastic interpolation on the anchor keyframe (`EASE_OUT` for arrival, `EASE_IN` for departure)
4. Sets `amplitude` and `period` on that keyframe from the panel sliders
5. Marks the overshoot keyframe as `BREAKDOWN` type (cyan) so it is visually distinct

Animator owns all keyframes after Apply. To redo: delete the cyan BREAKDOWN key, change settings, Apply again.

## Ubiquitous Language

| Term | Definition |
|---|---|
| **Anchor keyframe** | The animator's original keyframe — the target position the mechanical object reaches |
| **Overshoot keyframe** | The duplicate keyframe added by the add-on, placed at `anchor_frame ± Duration`. Same value as anchor. Type: BREAKDOWN (cyan). |
| **Arrival settle** | Effect placed AFTER the anchor keyframe. Object reaches target, overshoots, oscillates back. `EASE_OUT`. |
| **Departure kick** | Effect placed BEFORE the anchor keyframe. Object briefly moves opposite to direction of travel before the main motion begins. `EASE_IN`. |
| **Duration** | Number of frames between anchor keyframe and overshoot keyframe. Controls how long the elastic effect lasts. |
| **Amplitude** | Overshoot strength. Maps directly to Blender's `keyframe.amplitude`. Controls how far past the target the object goes. |
| **Period** | Bounce tightness / decay rate. Maps to Blender's `keyframe.period`. Low = tight stiff mechanism, high = loose slow-decaying bounce. |
| **Before/After toggle** | Selects departure kick (Before) or arrival settle (After). Controls time direction of the overshoot keyframe placement and the easing type applied. |
| **Flat segment** | The two-keyframe region (anchor + overshoot) that holds the same value. Elastic interpolation lives inside this segment only. |
| **Guard check** | Pre-apply validation. Warns if the keyframe adjacent to the anchor (in the Before/After direction) does not have a matching value — would indicate the flat segment assumption is broken. |

## Design Decisions

### Why elastic interpolation instead of FNGENERATOR modifier

Blender's native elastic easing (`keyframe.interpolation = 'ELASTIC'`) with `amplitude` and `period` properties produces exactly the correct damped sinusoidal shape. The FNGENERATOR SINC approach required a `phase_offset = 2.7` hack because SINC peaks at x=0 rather than starting at zero — wrong shape for an additive settle. Elastic is the right primitive.

### Why duplicate keyframe at same value

Elastic interpolation spans the full segment between two keyframes. By duplicating the anchor keyframe (same value) N frames away, the elastic oscillation is contained within a flat-value segment. The object arrives, wiggles around the arrived value, and settles — all within the Duration window. No bleed into adjacent motion segments.

### Why BREAKDOWN keyframe type

`keyframe.type = 'BREAKDOWN'` renders cyan in the timeline and graph editor. Gives animator immediate visual distinction between their own keys and add-on-generated keys. Also used by the guard check to identify existing overshoot keyframes. No Remove operator needed — animator deletes BREAKDOWN keys manually.

### Why no Remove operator

Animator is responsible for their keyframes post-Apply. To change settings: delete the cyan BREAKDOWN key, adjust sliders, Apply again. Simpler mental model. No fragile tracking of which keyframe belongs to which.

### Why no keyframe tracking / follow feature

Tracking anchor keyframe movement after Apply requires either a polling timer (fragile, like the old prototype) or metadata that desyncs when animator moves keys manually. Scope not worth the complexity for v1. Add-on is a one-way macro.

### Why per-keyframe (not per-segment pair)

Departure and arrival are the same mathematical shape with different time direction. A single per-keyframe tool with a Before/After toggle handles both cases without requiring the animator to always select exactly 2 keyframes. Simpler selection model.

## Parameters (v1 Panel)

- **Duration** — integer, frames, min 1
- **Amplitude** — float, overshoot size
- **Period** — float, bounce tightness (low = stiff, high = loose)
- **Before / After** — enum toggle (departure / arrival)

## Hard Constraints

**Settle must be exact.** The oscillation must finish precisely at the anchor keyframe's value — no residual offset, no drift. This is guaranteed by the duplicate-same-value approach: both the anchor keyframe and overshoot keyframe hold the identical value, so the curve is pinned exactly at both ends. The elastic oscillation only exists between them. The add-on must never expose value_offset or any parameter that could cause the overshoot keyframe to deviate from the anchor value.

**Batch apply is a primary use case.** Animator selects all mechanical keyframes across all fcurves in a scene, hits Apply once, and the effect is added to all of them with the current panel settings. Single-keyframe and multi-keyframe workflows must both work in one operator call.

## What This Is Not

- Not a modifier — it adds keyframes
- Not non-destructive in the modifier sense — but the BREAKDOWN color keeps it manageable
- Not a follow/tracking system — static placement at Apply time
- No baked complex math — pure native Blender elastic interpolation

## Out of Scope (v1)

- Multi-fcurve batch apply in one click (possible future)
- Preset saving
- Live follow when anchor keyframe is moved
- Remove operator
