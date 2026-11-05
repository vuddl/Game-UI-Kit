# Mockup layout format

One file per screen at `ui_art/<kit>/mockups/<screen>.json`. Items draw in list order, so later items sit on top.

```json
{
  "size": [1080, 1920],
  "background": "#1E2A44",
  "reference": "style/references/shop.png",
  "items": [
    {"element": "panels/shop_panel", "x": 540, "y": 960, "w": 980, "h": 1400, "anchor": "center"},
    {"text": "Cửa hàng", "x": 540, "y": 330, "w": 700, "h": 90, "anchor": "center", "text_size": 64, "text_stroke": 3},
    {"element": "buttons/btn_buy_normal", "x": 540, "y": 1500, "w": 420, "h": 130, "anchor": "center", "text": "Mua", "text_size": 48},
    {"element": "icons/ruby", "x": 200, "y": 700, "w": 140}
  ]
}
```

## Layout keys

| Key | Meaning |
|---|---|
| `size` | Required. Screen `[width, height]` in pixels. Use the reference's size when there is one, so positions can be measured directly. |
| `items` | Required. The list of items. |
| `background` | Hex color, or an element name stretched to fill the screen. |
| `reference` | Image path relative to the kit. Also writes `<screen>_vs_reference.png`. |
| `font` | Font file path for sample text. A common system font is used otherwise. |

## Item keys

| Key | Meaning |
|---|---|
| `element` | Element name from the manifest. An item needs `element`, `text`, or both. |
| `text` | Sample text, centered in the item's box and shrunk to fit. |
| `x`, `y` | Required. Position of the `anchor` point on screen. |
| `w`, `h` | Size. Both set a box. One keeps the sprite's proportions. Neither uses its native size. |
| `anchor` | `top_left` by default, or `top`, `top_right`, `left`, `center`, `right`, `bottom_left`, `bottom`, `bottom_right`. |
| `mode` | `auto` by default: 9-slice if borders are ready, otherwise fit inside the box without distortion. Also `nine`, `fit`, `stretch`. |
| `border_scale` | Multiplies 9-slice corner size, for when the mockup resolution is much higher than the sprite. |
| `opacity` | From 0 to 1, for overlays and dimmed backdrops. |
| `text_color`, `text_size`, `text_stroke` | Text color, pixel size and outline width. |

## Notes

- Show a progress bar with its track and fill as two items, and set the fill's `w` to the value shown.
- Use `_pressed` or `_disabled` elements only to show those states, otherwise `_normal`.
- A missing element draws as a red `MISSING` box and exits with status 2.
- Unknown keys are rejected, so a typo cannot silently change the layout.
