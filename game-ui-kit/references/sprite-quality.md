# Sprite fidelity, clean edges and material alpha

Use for PNG production, reconstruction from flattened demos and repairs to an existing kit. Preserve approved designs and originals. An authorized repair reuses submitted export formats/layouts; it does not require reopening forms to reconfirm the same work.

Respect the current repair scope. A request for one or two review samples does not authorize regenerating the kit or replacing approved components. A discussion or instruction-only skill update produces no new assets. When the user asks to review criteria or says to wait for a start signal, record the criteria and wait for that signal before dependent changes; do not add a new approval gate to otherwise authorized work.

## Resolution and contours

Measure the largest actual placement of each asset. Restore a small/blurry component at sufficient native resolution while preserving its approved appearance. Use native geometry only when it can reproduce the reference's complete geometry, materials, volume and lighting. `scripts/native_ui.py` renders kit-owned parametric specs into internal body/mask/shadow/glow files; its defaults are draft settings, not a substitute for matching a reference. Keep complex icons and illustrations as artwork; use built-in image generation for faithful reconstruction rather than flattening them into simple shape traces. For a character, lock identity, expression, hair, clothing, pose, hand anatomy and crop.

Measure the generator's actual output, split crowded sheets when necessary, and inspect detail at the real placement size. Interpolation, sharpening or a 4K prompt does not prove recovered detail. Record remaining native-resolution limits.

Quality restoration must preserve the reference's appearance, including its convex volume, bevel depth, rim widths, light direction and shaped soft reflections. Matching only the outline is insufficient. Do not replace a dimensional painted button with a flat generic gradient or a hard ellipse highlight. For a uniform polished material, reject cloudy patches, grain and random color mottling even when the render prompt requested smooth color. If numerical smoothing is needed, work only within that material's lighting field and protect its bevel, highlights, rim and approved contour; never blur the entire component.

Additional mask feather defaults to **0** (`slice --ramp 0`). Retain antialiasing only at the immediate contour. Eliminate pixel-level wobble, grain, matte residue and colored halos; preserve thin strokes and meaningful cutout holes. Do not blur the entire mask to hide a bad edge.

Keep an already clean RGBA contour unchanged. Do not threshold it, run a median over it or replace it with an interpolated binary silhouette just to normalize interior opacity. The repair helper defaults to `edge_policy: "preserve"`; it repairs declared solid interiors while retaining boundary alpha. `edge_policy: "rebuild"` explicitly opts into contour/matte reconstruction when the existing cut actually needs replacement, followed by visual review. Mixed materials require a solid-region mask in preserve mode. A preserve-mode source used with a new effect must already be body-only, otherwise the old and new effects would stack.

Import clean isolated PNGs directly with `uikit.py import --map`. Do not route them through sheet segmentation merely to change opacity or naming; after cutting an actual sheet, visually check that low-coverage edge pixels and fine wisps survived its segmentation and trim.

## Body, transparency and effects

Classify each resource/material in `style/sprite_quality.json`: `opaque`, `mixed`, `translucent` or `background`. Unknown intent needs inspection. A solid body has alpha 255 internally, not mottled 252/253 values. Mixed glass/metal needs an explicit mask for its solid regions. Keep intentional glass, hair, smoke and VFX coverage; do not globally flatten them.

Define a solid-region mask from the intended material and silhouette, not merely from pixels whose current alpha is already near 255. That would exclude interior opacity defects from the very checks intended to find them. For a known closed opaque button, repair the entire interior while preserving the narrow antialiased contour; inspect it on both black and white to reveal low-alpha speckles.

Inspect RGB and alpha independently when a surface looks dirty: uneven opacity can produce apparent color noise even when the foreground RGB is smooth. Correct only defects; preserve intentional texture and material detail rather than applying universal smoothing to hair, fabric or illustrations.

Remove contaminated outer shadow/glow, isolate the main artwork, and reconstruct effects independently. A monochromatic effect has a stable straight RGB hue and a continuous alpha field governed by direction, distance, spread and blur. Deliberately colored VFX may use multiple explicitly described layers.

This separation is an internal production step. Deliver one composed PNG per asset by default; deliver separate body/shadow/glow files only when explicitly requested. For clean shadows, compute the fade from a declared silhouette with a normalized Gaussian or another specified continuous falloff in floating-point alpha. Keep RGB constant, combine optical contributions in alpha, check outward fade and unclipped margins, and quantize once at final export. A generated shadow that looks blotchy must be rebuilt, not accepted because its prompt mentioned smoothness.

### Match the reference's effect strength

A smooth effect can still be wrong because it is too faint, too blurred or too wide. Match its visual weight to the approved demo at the same displayed body size and against the same or a comparable local background. Do not equate higher quality with weaker shadows, softer edges or a larger blur, and do not reuse the last button's numeric settings for unrelated assets.

For each visible effect, assess its source hue, peak opacity or brightness, contrast against the local background, contact density, direction, offset, spread, blur radius and fade extent. Keep spread and blur separate: a wide faint haze does not replace a compact dense contact shadow. Check glow's peak brightness/saturation and extent as carefully as shadow's darkness. Preserve separate contact and ambient contributions, inner shadows and bevel lighting when the reference shows them.

Estimate these parameters from the reference and record the chosen values or qualitative comparisons with the asset's reconstruction notes/spec. Choose values in the final sprite's scale and document whether each size is in pixels or relative units. When working enlarged, scale spatial parameters consistently; opacity is not a spatial parameter. Account for the reference's backdrop and intended compositing when judging contrast. If a flattened screenshot leaves the original tint/opacity ambiguous, label the estimate and match its rendered appearance rather than claiming exact recovery.

The defaults in renderers and shape recipes are starting values only. Tune intensity and falloff independently; compare the reconstructed effect and the assembled sprite to the demo before declaring them matched. `effect_alpha` computes a normalized floating-point Gaussian field with caller-supplied opacity, blur and offset; it does not choose or certify reference fidelity.

**Resize effect alpha separately and reapply its hue.** Premultiplied RGBA resize followed by unpremultiplication at low alpha can quantize RGB into mottled colors. Composite the resized body/effects afterward. Do not encode shadow falloff as different RGB colors sampled against one backdrop.

In the source renderer's compositing space, `C = alpha*F + (1-alpha)*B`. Visible color C already mixes foreground F and backdrop B; it is not the reusable foreground color. Identify B and estimate the material's tint/opacity from surrounding scenery, solid regions or multiple references. With known B and alpha, use `F = (C-(1-alpha)*B)/alpha`; linearize first when that is how the renderer composites. One flattened reference cannot uniquely determine both F and alpha. Alpha zero contains no foreground color evidence. Record estimates and limits rather than claiming exact recovery.

Rebuild accidental uneven translucency from an inferred tint and a smooth alpha model, with reflections separate. Preserve adjacent contents/frames. Neutral highlights on metal are not evidence of glass: protect hardware with an explicit material mask or exclusion polygons before replacing pane pixels. A scenery plate with transparent holes needs scene reconstruction, not opacity flattening.

## Proof before delivery

Use `scripts/sprite_quality.py` for declared-material alpha audits, region repair, inverse compositing and constant-hue effects. Numerical checks do not certify a silhouette or material classification.

1. Inspect RGB and alpha separately. Compare the final component to the **approved demo/reference**, as well as the previous version, at the **same displayed body size**. Empty padding must not change the apparent scale. Check silhouette, proportions, hue, material, volume, bevel and highlight shape; a cleaner redesign is not a fidelity pass. Also inspect white, black, gray and saturated contrasting backgrounds at delivery size and zoomed in for fringe, interior mottling/holes and intentional transparency.
2. Inspect internal standalone effects and the assembled sprite. Check hue stability, continuous opacity, direction and unclipped falloff, then explicitly compare shadow darkness/contact density and glow brightness, softness, spread and fade extent to the demo on its local background. Multiple-backdrop checks reveal defects; they do not replace this reference-strength comparison.
3. Recompute 9-slice from final canvases and inspect real small/stretched uses. Keep ornaments without a stretch band at fixed aspect ratio.
4. Reassemble affected demos from corrected assets. Keep dimensions, resources, current background proofs and delivery metadata synchronized.
5. Set `quality_required: true` in every new or repaired export brief. Save the `check_kit` results (current pixel/mask hashes and material modes), with individual `visual_reviewed` decisions and notes on appearance/effect-strength comparison, in `export/sprite_quality_report.json` only after inspection. Packaging rejects unknown intent, failed solid-core checks and missing/stale review proofs. Changing an asset, its material classification or its solid-region mask requires another review. Numerical tests cannot certify style, likeness or effect strength. Do not bypass this gate or mark an asset reviewed from file existence.

Preserve previous sprites for comparison. Fix or explicitly report unresolved edge, material or resolution defects before claiming the affected asset ready.
