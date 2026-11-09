# Shape recipes

A recipe rebuilds one sprite from editable Photoshop shapes and layer effects, so the PSD can be edited layer by layer instead of holding a picture. One file per element at `style/recipes/<element>.json`, such as `style/recipes/frames/frame_activity_home.json`. The PSD export uses a sprite's recipe whenever one exists and is valid.

## Workflow

1. `uikit.py recipe ui_art/<kit> --auto` writes a first guess for every simple sprite: a rectangle, rounded rectangle or ellipse with its fill or vertical gradient, and its border as a separate stroke layer. Sprites that are not a simple shape print `NO_SIMPLE_SHAPE`.
2. View each board in `preview/recipes/<element>.png`: the source, the shape rebuild and the difference. The command prints the difference; 6 or less is hard to notice.
3. Edit the recipe until it matches by eye: add the bevel, shadows, gloss, inner panels and decorations the sprite has, each as its own layer. Run `uikit.py recipe ui_art/<kit> --match "<element>"` again after each edit and view the board.
4. Write recipes by hand for sprites the guess cannot handle but shapes can: icons from circles, rounded rectangles and `path` polygons, ribbons and badges from paths. Leave only real illustration as images: characters, scenery, detailed items.

The renderer approximates Photoshop, so a small difference that remains in soft effects is fine. The final check is `export/psd/assets/<layout>_check.png`, which Photoshop itself saves.

## Format

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

- **A border:** its own shape with `fill_opacity` 0 and a `stroke` effect, in a group named `stroke`, as in the example. A double border is two such layers.
- **Thickness, a raised or pressed look:** `bevel` on the fill. Use `direction` `down` for a pressed state.
- **Gloss and shine:** a white `ellipse` or `rect` with a gradient from transparent to white, `clip` to the shape below when it must not spill out.
- **A dark lip under a button:** a second shape below the fill, moved down a few pixels, in a darker color; or `drop_shadow` with `spread` 100 and `size` 0.
- **Inner panels and plates:** further shapes on top, each with its own effects.
- **Repeated surface texture:** Photoshop patterns cannot be created by script, so draw the motif with shapes, or keep that part as an image layer clipped to the shape and say so.
