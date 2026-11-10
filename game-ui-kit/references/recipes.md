# Shape recipes

A recipe describes an editable Photoshop shape stack for one sprite. Keep one file per element at `style/recipes/<element>.json`, such as `style/recipes/frames/frame_activity_home.json`. The PSD export uses a valid recipe for elements routed to native UI. Follow [Photoshop source and export](photoshop.md) to decide which elements to rebuild and how to verify them.

## Workflow

1. For an element that needs a shape stack, use `uikit.py recipe ui_art/<kit> --auto --match "<element>"` to draft a recipe for simple geometry. Sprites that the guess cannot handle print `NO_SIMPLE_SHAPE`. Write those constructions by hand if the recipe format fits.
2. View the source, the shape rebuild and the difference on the board in `preview/recipes/<element>.png`. The numeric difference is a recipe-renderer diagnostic.
3. Refine the shape and native effects, using separate layers only for features that need independent edits. Run `uikit.py recipe ui_art/<kit> --match "<element>"` to review changes.
4. Use Photoshop directly for native features beyond this schema, such as smooth compound Bézier paths or clipping a placed image Smart Object to a shape. Render and verify the saved Photoshop document against the approved reference.

The recipe renderer approximates Photoshop. Use the Photoshop render for the final fidelity check. The screen export initially writes that render to `export/psd/assets/<layout>_check.png`.

## Format

This example separates the stroke because its relief is independent of the face. Use the approved reference to choose the geometry and effect settings for each element.

```json
{
  "element": "frames/frame_activity_home",
  "size": [240, 240],
  "layers": [
    {"name": "fill_rounded_rectangle", "shape": "rect", "box": [4, 4, 236, 236], "radius": 44,
     "fill": {"gradient": [["#f6e2ba", 0], ["#fff6de", 100]], "angle": 90},
     "effects": {"bevel": {"size": 14, "depth": 90, "angle": 90, "highlight_opacity": 40, "shadow": "#c99a5e", "shadow_opacity": 55}}},
    {"group": "stroke", "effects": {"bevel": {"size": 3}}, "layers": [
      {"name": "stroke_rounded_rectangle", "shape": "rect", "box": [4, 4, 236, 236], "radius": 44,
       "fill": "#ffffff", "fill_opacity": 0, "effects": {"stroke": {"size": 8, "color": "#30c7d5", "position": "inside"}}}
    ]},
    {"name": "highlight_top_left", "shape": "ellipse", "box": [22, 18, 70, 40],
     "fill": {"gradient": [["#ffffff", 0, 30], ["#ffffff", 100, 95]], "angle": 90}}
  ]
}
```

Coordinates are pixels of the sprite at its own size. Layers go bottom to top. When the sprite is placed larger, smaller or 9-sliced, the export moves the boxes with it and scales radii and effect sizes by the corner scale, so corners keep their look.

### Layer keys

| Key | Meaning |
|---|---|
| `name` | Layer name: what it is and its shape, such as `fill_rounded_rectangle`, `stroke_rectangle`, `highlight_top`, `shadow_bottom`, `icon_star`. |
| `shape` | `rect` (with `radius`), `ellipse`, or `path`. Rects and ellipses become live shapes, so their size and corner radius stay editable in Photoshop's Properties. |
| `box` | `[x0, y0, x1, y1]` for `rect` and `ellipse`. |
| `radius` | Corner radius, or `[top_left, top_right, bottom_right, bottom_left]`. |
| `points` / `subpaths` | A polygon as `[[x, y], ...]`, or several, combined even-odd so holes work. |
| `fill` | `"#rrggbb"`, or `{"gradient": [[color, position 0-100, opacity 0-100], ...], "angle": 90}`. Angle 90 runs from the first stop at the bottom to the last at the top; -90 runs top to bottom. |
| `fill_opacity` | 0-100. Hides the fill but keeps the effects, for a layer that is only a stroke or a glow. |
| `opacity` | 0-100, the whole layer. |
| `blend` | `normal`, `multiply`, `screen`, `overlay`, `soft_light`, `hard_light`, `color_dodge`, `color_burn`, `darken`, `lighten`, `linear_dodge`, `linear_burn`. |
| `clip` | `true` clips the layer to the layer below as a clipping mask, such as a gloss that must stay inside the panel. |
| `effects` | Layer style, below. |

A **group** is `{"group": "<name>", "layers": [...], "effects": {...}, "opacity": 100, "blend": "normal"}`. Effects on a group apply to everything in it together, such as one bevel over a border made of several shapes. The recipe's own top-level `effects` go on the element's group.

### Effects

Sizes and distances are pixels; opacity is 0-100; angles are degrees as in Photoshop, where 90 is light from above and 120 from the upper left.

| Effect | Keys, with defaults |
|---|---|
| `stroke` | `size` 3, `color` or `gradient` with `angle`, `position` `outside` (or `inside`, `center`), `opacity` 100, `blend` |
| `bevel` | `style` `inner` (or `outer`, `emboss`, `pillow`), `technique` `smooth` (or `chisel_hard`, `chisel_soft`), `depth` 100, `direction` `up` or `down`, `size` 5, `soften` 0, `angle` 120, `altitude` 30, `highlight` white, `highlight_opacity` 75, `shadow` black, `shadow_opacity` 75 |
| `drop_shadow` | `color` black, `opacity` 75, `angle` 120, `distance` 4, `spread` 0, `size` 6, `blend` `multiply` |
| `inner_shadow` | the same as `drop_shadow` |
| `outer_glow`, `inner_glow` | `color`, `opacity` 75, `size` 10, `spread` 0, `blend` `screen` |
| `gradient_overlay` | `gradient`, `angle` 90, `opacity` 100, `blend` |
| `color_overlay` | `color`, `opacity` 100, `blend` |

Any effect takes `"enabled": false` to keep it in the file but switched off.

## What to use when

- **Flat outline.** Apply `stroke` directly to the primary shape.
- **Outline with relief.** Use a matching shape with `fill_opacity` 0 and `stroke`, then apply `bevel` to its group. Apply a group-level stroke for a continuous outline around several parts.
- **Rounded thickness.** Apply `bevel` to the primary shape. Add a separate shape for a visible lip or distinct surface that needs independent edits.
- **Gloss or local shadow.** Use a gradient or layer effect matched to the material. Set `clip` for a separate reflection or shadow that must stay within its receiving surface.
- **Repeated surface texture.** Use a native pattern in Photoshop if appropriate, or keep the source texture as an image clipped to the shape. Finish this in Photoshop when the recipe schema cannot represent the construction.
