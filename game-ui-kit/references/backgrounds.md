# Background separation and multisize

Use for a demo UI mockup supplied by the user or approved during concept review, and for a clean background that needs to support multiple screen ratios. Keep the original file. Artwork recognition, separation, inpainting and outpainting use visual inspection and the built-in `image_gen` tool. `scripts/background.py` performs geometry calculations and QA rendering; it does not identify or paint objects.

## Identify the background and its important content

Inspect the original at full resolution. Tell the user in Vietnamese what will become the background: for example sky, terrain, distant buildings and scene lighting. Identify separately:

- Baked UI to remove: buttons, bars, panels, counters, interface text and their UI-only shadows or glow.
- Scene subjects to protect: the actual hero, landmark, horizon feature or other focal artwork. A character on a scenery background may be a scene subject; a portrait inside a UI card is a separate asset. Judge from the demo and the brief.
- Foreground artwork that needs independent positioning or scale: characters, large props, framing foliage and effects. Keep those as separate full-resolution transparent assets when a single plate cannot preserve the composition across the required ratios.
- Background hidden under UI, which must be reconstructed. Describe those areas as inferred scenery; a flattened demo cannot reveal its exact hidden pixels. Remove UI contamination and halos without deleting intentional scene details.

Record the source image and this classification in `briefs/backgrounds/<screen>_analysis.md`. Use the user's specific keep/remove instructions. Ask only when an ambiguous scene-versus-UI classification changes the intended result. For a popup's blurred parent screen, prepare the parent's clean scene first; UI intentionally visible in a derived blurred screenshot stays a separate composite backdrop, not the reusable clean scenery master.

## Calculate expansion before generating

Use device sizes/aspect ratios already in the brief, chat or optional `background_targets` form answer. Resolve ratio-only requests to explicit test resolutions and state them. Otherwise use `background.default_targets(base_size)`: the actual base size plus portrait 1080x1920, 1080x2400 and 1536x2048; swap the latter pairs for landscape. State this working range. A new orientation or a ratio outside that range needs another check.

Start with a plan that protects the whole source frame. For original width `W`, height `H` and requested ratio extremes `r_min`, `r_max`, a centered expanded master needs at least:

```text
master_width  >= max(W, H * r_max)
master_height >= max(H, W / r_min)
```

The helper adds two source pixels for integer-placement safety and rounds canvas dimensions up to multiples of four. It reports each side's expansion and the original frame's position. This is a conservative starting point. It may make the scene look smaller at the base ratio; inspect that composite and refine the protected regions, separation or aspect-specific variants when necessary. Do not crop important content to hide a failed plan.

```bash
py -3 <skill>/scripts/background.py plan ui_art/<kit> --source style/concepts/home.png --target 1080x1920 --target 1080x2400 --target 1536x2048 --out briefs/backgrounds/home_plan.json
```

Use the resulting canvas and original frame in the edit prompt. Preserve their scale, horizon, perspective, lighting and scene identity as far as the edit permits. Extend only what the composition requires: more sky, ground or scenery on the calculated sides. Reconstruct under UI at the same time when practical. Do not fill margins with mirrored edges, repeated strips, blurred padding, flat bands or an enlarged copy of the whole scene. Use an opaque clean plate for the full-screen scene, with transparency reserved for separate foreground layers.

Count cleanup/outpainting and foreground isolation calls in the announced generation scope, reusing any approval already given. Read the `imagegen` skill, view local sources before edits, and use the built-in tool with the source as an edit target. This workflow edits background artwork; UI mockups continue to be assembled from real sprites. Keep user originals unchanged.

### Background edit prompt

```text
Asset: full-screen game scenery background, no interface overlay.
Edit target: <demo or clean source, exact file>.
Remove UI: <identified controls, interface text, panels, UI-only shadows and glows>.
Retain as scenery: <identified scene elements, horizon and important subjects>.
Separate foreground assets: <objects that will be isolated independently, if any>.
Reconstruct: <areas hidden by UI; infer continuous scenery from visible context>.
Canvas plan: <master width x height>, original frame <x, y, width, height>.
Extend: left <pixels>, right <pixels>, top <pixels>, bottom <pixels>.
Composition: preserve scene identity, perspective, lighting and proportions;
keep <important subjects> within <measured protected region>;
retain quiet areas behind <UI regions> at the target aspect ratios <range>.
Avoid: UI remnants, altered main subjects, seams, repeated or mirrored edge
strips, blurred padding, stretched scenery and new watermarks.
Output: only a clean opaque background plate, full available resolution.
```

## Measure the actual result and attach a profile

Inspect the generated file and measure its actual dimensions, subject rectangles and alignment. The tool may return a different size or placement from the requested plan. Never copy planned coordinates blindly or claim extra detail by upscaling. If resolution is insufficient for the largest target, regenerate within the available tool's capabilities or report the limit. Keep the complete expanded master; screen exports are cropped views of it.

Import the master through `uikit.py import` with a map, retaining its dimensions. For an image already inside the kit, use `--map` explicitly (the automatic import scan excludes kit-owned files). Example map line: `bg_home_master.png = backgrounds/bg_home`. Do not run scene backgrounds through sprite trimming, key-color removal or 9-slice.

Write `briefs/backgrounds/home.json` from those actual measurements:

```json
{
  "image": "elements/backgrounds/bg_home.png",
  "source_demo": "style/concepts/home.png",
  "targets": [[1080, 1920], [1080, 2400], [1536, 2048]],
  "alignment": [0.5, 0.5],
  "protected": [
    {"name": "Main landmark", "rect": [420, 700, 500, 900], "max_crop": 0}
  ]
}
```

`rect` is `[x, y, width, height]` in actual master pixels, with origin at top left. Use one rectangle per important object; include intentional effects in its bounds. `max_crop` is the maximum fraction of that rectangle's area allowed to leave the viewport, default zero. Keep all main subjects fully visible unless the user approved a specific partial crop. Use `protected: []` only when the inspected background is abstract or has no critical subjects, and record that judgment. `alignment` is a fraction of available overflow from left/top, not the subject's normalized position.

In each layout set `background` to the imported element and `background_profile` to that profile path. Separate screens/compositions need their own assessment. Share a master/profile only when its composition and target range really apply to those screens.

## Check the clean plate and the UI composite

```bash
py -3 <skill>/scripts/background.py check ui_art/<kit> --profile briefs/backgrounds/home.json
py -3 <skill>/scripts/background.py check ui_art/<kit> --profile briefs/backgrounds/home.json --layout home__v1
```

The boards are saved separately as `preview/backgrounds/<profile_name>__clean.png` and `<profile_name>__<layout>.png`. The second renders the actual layout's UI on each target, using the same uniform-cover function as PNG mockups. Check each affected layout variant; the report retains current overlay proofs separately. Target sizes must include its actual base resolution.

For master `Mw x Mh` and viewport `Vw x Vh`, use:

```text
s = max(Vw / Mw, Vh / Mh)
display_size = (Mw * s, Mh * s)
top_left = ((Vw - Mw * s) * alignment_x,
            (Vh - Mh * s) * alignment_y)
```

One scale applies to both axes. Crop overflow at the viewport. The checker measures protected-area visibility and fails opaque full-screen plates with transparent holes. It writes `export/backgrounds/<profile_name>.json` with actual dimensions, source/profile hashes, visible crop bounds, placement and subject visibility at each target. Profile-based PNG, PSD and Unity exports reject missing, stale or failed checks, and require a current overlay check for the exported layout variant. An overlay proof becomes stale when that layout changes.

**Geometric PASS still needs visual review.** View full-size output for clean reconstruction, seams, correct proportions, acceptable scene scale and a coherent composition. View the UI boards for subject occlusion, busy imagery behind labels, horizon placement and useful negative space. A bounding-box calculation cannot identify UI contamination, understand artwork, or decide whether UI covers a face. Inspect intermediate ratios within the declared range as well as its extremes; protect critical subjects with zero cropping. If any miss is unacceptable, extend/recompose, adjust alignment, separate foreground layers or propose variants for narrower aspect ranges, then remeasure and check again. Record findings and any remaining limits in `briefs/backgrounds/<screen>_review.md`; do not report the art as verified from numeric checks alone.

## Deliver and guide Unity assembly

Deliver the full clean expanded background PNG, any separately isolated foreground PNGs, the profile, multisize board, report and assembly JSON with the screen exports. Keep the full master inside the Photoshop Smart Object. The screen PSD's viewport crop must match the PNG rendering; off-canvas scenery remains available for other sizes.

The Unity JSON's `backgroundRendering` describes a Simple Image using a Full Rect sprite under a full-viewport background parent, independent of the UI safe-area panel. Use uniform cover and the supplied alignment; do not use nonuniform stretch, sliced images or fit-inside letterboxing for the scene. For a centered crop, an Aspect Ratio Fitter in Envelope Parent mode is a suitable implementation. For custom alignment, implement the recorded scale/position formula in the parent's local coordinates, with Unity's Y direction converted. `Image.preserveAspect` alone is not a cover layout. Background scaling and Canvas Scaler behavior are separate decisions; the existing height-based UI simulation is a preview of the assembly guide, not proof of device-specific anchors or cutout behavior.

Keep essential subjects out of actual cutouts/obscuring UI, using supplied safe-area insets and a Unity device preview when available. Never shrink the full-screen background into the UI safe area. State the tested sizes, inferred anchors that need adjustment, upscaling limits and any untested devices/ratios. The skill delivers art and an assembly guide; it does not silently create Unity scenes or prefabs.

Official implementation references: [Unity Aspect Ratio Fitter](https://docs.unity3d.com/Packages/com.unity.ugui@2.0/manual/script-AspectRatioFitter.html), [Unity UI at multiple resolutions](https://docs.unity3d.com/Packages/com.unity.ugui@2.0/manual/HOWTO-UIMultiResolution.html).
