# Exact reusable sprite masters during demo design

Use automatically after a screen is approved, including legacy approved demos when resuming. Internal reuse is separate from production/export authorization. Build incrementally from actual approved components; do not generate a whole generic base sheet merely because one demo was approved. The user reviews complete demos, not each internal sprite.

## Sources and extraction

Inspect the earliest usable approved source/master at the needed native size. Use already available original layered/source sprites first. Retain exact artwork for shared avatars, icons, frames, buttons, panels, lettering and decorations. Never repeatedly crop a shrinking later demo or ask the model to redraw the same component to make another screen.

`workflow.py approve` preserves the exact image and queues its sources in `style/reusable_components.json`. Extract chosen regions once with:

```text
py -3 <skill>/scripts/workflow.py component <kit> --id player_avatar --source style/concepts/lobby__approved.png --box 20 30 220 230
```

Coordinates are left, top, right, bottom in original pixels. The helper only accepts a recorded approved image and stores a lossless native-size master and its source/hash/rectangle under `style/components/`. It does not infer transparency: a crop with baked scenery remains a composite region, not a transparent sprite. Inspect alpha and edges. Use original layers or a deterministic mask when actual isolation is required, preserving approved visible pixels and their soft alpha. Do not silently regenerate an illustration for isolation. Report a genuine source/resolution limitation rather than claiming an approximate reconstruction is identical. A whole approved screen is not a reusable component library by itself.

An existing component ID cannot be overwritten unless the user requested a design change. `--replace` preserves the previous master; do not use it for unrelated screen revisions. Keep unchanged masters stable when adding new approved screens. Record source/role and meaningful variants; labels/data that change between screens may be separate layers, retaining the approved font and effects. Unchanged lettering must not drift between image generations.

## Assemble and revise

Compose real masters using existing `uikit.py` layout/9-slice tools or `workflow.py compose`. Import clean PNG masters through `uikit.py import --map` when production layouts need element IDs; don't hand-edit the manifest. Reuse sprites as actual layers even in early demo alternatives, not just as reference images in a full-screen generation prompt.

For the lightweight exact compositor, save an internal layout such as:

```json
{
  "size": [1920, 1080],
  "background": "style/plates/lobby.png",
  "components": [
    {"id": "player_avatar", "x": 24, "y": 24}
  ]
}
```

```text
py -3 <skill>/scripts/workflow.py compose <kit> --file <layout.json> --output style/concepts/lobby__concept_2.png
```

It verifies master hashes and pastes the original pixels. A background must already match the canvas. Scaling is opt-in per placement (`allow_scale: true`, matching width/height ratio), done once from the master, with nearest-neighbor for declared pixel art; do not repeatedly resize a previously rendered copy. Prefer original-size placement and 9-slice only where the component's approved structure permits it. No automatic upscaling, sharpening, palette changes, smoothing or restyling of reused artwork.

Generate only missing artwork or the specifically requested design change, in the approved style. Composite it with the unchanged original sprites before showing the result. Revisions must not regenerate an entire screen containing existing reusable components; preserve unchanged scene/UI layers and their typography. Additional backgrounds/poses needed by a new screen may be designed within scope, but do not replace an unchanged avatar or icon for convenience.

Inspect at equal visible size against the master and compare the full composite. Detect drifting faces, hair, hands, proportions, lettering, border weight, material or alpha. A similar-looking new generation is not exact reuse. Sprite cropping and composition are deterministic operations; use image generation for new art, not to copy/paste an existing component. The production quality/edge/background checks still apply when assembling/exporting deliverables. Only requested formats are exported.
