# Mockup layout format

One file per screen at `ui_art/<kit>/mockups/<screen>.json`, or `<screen>__v1.json`, `<screen>__v2.json` for variants. Items draw in list order, so later items sit on top.

```json
{
  "size": [1080, 1920],
  "background": "#1E2A44",
  "reference": "style/references/shop.png",
  "items": [
    {"element": "panels/shop_panel", "x": 540, "y": 960, "w": 980, "h": 1400, "anchor": "center"},
    {"text": "Cửa hàng", "x": 540, "y": 330, "w": 700, "h": 90, "anchor": "center", "text_size": 64, "text_stroke": 3},
    {"element": "buttons/btn_yellow", "x": 540, "y": 1500, "w": 420, "h": 130, "anchor": "center", "text": "Mua", "text_size": 48},
    {"element": "icons/ruby", "x": 200, "y": 700, "w": 140}
  ]
}
```

## Layout keys

| Key | Meaning |
|---|---|
| `size` | Required. Screen `[width, height]` in pixels. Use the reference's size when there is one, so positions can be measured directly. |
| `items` | Required. The list of items. |
| `title` | Screen name shown in the flow and demo. |
| `background` | Hex color, an element name, or an image path relative to the kit, stretched to fill the screen. |
| `reference` | Image path relative to the kit. Also writes `<screen>_vs_reference.png`. |
| `font` | Font file, relative to the kit or absolute. Defaults to the first file in the kit's `fonts/`, then a system font with a warning. |

## Item keys

| Key | Meaning |
|---|---|
| `element` | Element name from the manifest. An item needs `element`, `text`, or both. |
| `text` | Sample text, centered in the item's box and shrunk to fit. |
| `x`, `y` | Required. Position of the `anchor` point on screen. |
| `w`, `h` | Size. Both set a box. One keeps the sprite's proportions. Neither uses its native size. |
| `anchor` | `top_left` by default, or `top`, `top_right`, `left`, `center`, `right`, `bottom_left`, `bottom`, `bottom_right`. |
| `mode` | `auto` by default: 9-slice if borders are ready, otherwise fit inside the box without distortion. Also `nine`, `fit`, `stretch`. |
| `border_scale` | 9-slice corner size. By default corners shrink with the sprite and never grow, so set this only to override that, such as 2 when the screen resolution is far above the sprite's. |
| `fill` | From 0 to 1, for progress bars. `w` is the full width, the bar shortens from the right, and its round ends are kept. |
| `opacity` | From 0 to 1, for overlays and dimmed backdrops. |
| `text_color`, `text_size`, `text_stroke` | Text color, pixel size and outline width. |
| `goto` | Screen this item opens in the flow and demo, or `back`. Use the screen name without `__v1`. |
| `label` | Name for this item in wireframes and the flow, when it has no text. |
| `group` | PSD folder. Neighboring items with the same group share a folder, so keep them adjacent in the list. |

## Layout guide for rearranging

Use this to judge your own work, and adapt it to the game's genre and the user's references.

- Give each screen one obvious main action, and make it the largest and strongest in color.
- Keep related items together. Align to a shared grid with a few consistent gaps, and use the same size for items of the same rank.
- On phones, put frequent actions within thumb reach at the lower corners. Put status at the top and infrequent menus away from the thumbs. Avoid covering the center of a gameplay view.
- Keep tappable items at least about 7 percent of the screen's short side, and clear of edges and notches.
- Leave breathing room rather than filling every space, and move secondary actions into a menu when a screen is crowded.
- Keep text short and readable. Add a dark plate or outline when it sits on busy art.
- Label only what needs it. Universal icons such as settings, save, close, map, shop, jump and run need no caption. Keep text for values, such as currency, level and timers; for names the player must read, such as a mission; and for icons a new player could not guess. Fewer captions also mean larger icons.
- Take colors from the kit's palette. Group by tone, and keep the same surface treatment across all controls of one rank, so the screen reads as one set. Reserve the strongest accent for the main action.
- Follow the visual weight of the tone you chose. Light, translucent controls and heavy dark panels are different decisions, and mixing them looks wrong even if every color is on the palette.

The `mockup` command warns about small tap targets, items too near the edge or off screen, and edges that almost align. It cannot judge beauty, so always view the result.

## Notes

- Show a progress bar with its track as one item and its fill on top with `fill`, sized slightly inside the track.
- Use `_pressed` or `_disabled` elements only to show those states, otherwise the bare name, such as `btn_yellow`.
- A missing element draws as a red `MISSING` box and exits with status 2.
- Unknown keys are rejected, so a typo cannot silently change the layout.
