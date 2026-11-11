# Mockup layout format

One file per screen at `ui_art/<kit>/mockups/<screen>.json`, or `<screen>__v1.json`, `<screen>__v2.json` for variants. Items draw in list order, so later items sit on top.

```json
{
  "size": [1080, 1920],
  "background": "#1E2A44",
  "reference": "style/references/shop.png",
  "items": [
    {"element": "panels/shop_panel", "x": 540, "y": 960, "w": 980, "h": 1400, "anchor": "center"},
    {"text": "Shop", "x": 540, "y": 330, "w": 700, "h": 90, "anchor": "center", "text_size": 64, "text_stroke": 3},
    {"element": "buttons/btn_yellow", "x": 540, "y": 1500, "w": 420, "h": 130, "anchor": "center", "text": "Buy", "text_size": 48},
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
| `background` | Hex color, an element name, or an image path relative to the kit. Image backgrounds use uniform cover and crop overflow, preserving their proportions. |
| `background_profile` | Kit-relative JSON path, such as `briefs/backgrounds/home.json`. See [background multisize](backgrounds.md). Declares the actual master image, target sizes, protected subjects and top-left crop alignment. |
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
| `wf` | Wireframe kind, listed below. Only the wireframe uses it; an item with only `wf` draws nothing in the mockup. |
| `icon` | Wireframe icon name, listed below. |
| `sub` | Wireframe second line under the text, smaller. |
| `badge` | Wireframe red dot: `true`, a short text such as `"3"` or `"HOT"`, or `"+"` for the add button on a `pill`. |
| `selected` | Wireframe: `true` marks the current `tab`. |
| `align` | Wireframe text alignment: `left`, `center` or `right`. Text kinds default to `left` with a left anchor. |

## Wireframe items

Without `wf`, the kind is guessed from the element name, such as `buttons/` as `button` and `icons/` as `icon_button`, so set it whenever the guess would be wrong.

| `wf` | Draws | Typical use |
|---|---|---|
| `panel` | Translucent rounded surface | Section backgrounds, popup bodies |
| `card` | Raised card with icon and text; wide cards put the icon on the left | Offers, items, building info |
| `button` | Secondary button | Normal actions |
| `button_primary` | Large bright button | The screen's one main action |
| `icon_button` | Square button with icon and a short caption | Side features: daily, spin, mail |
| `pill` | Rounded value with icon, `badge: "+"` adds a plus | Currencies, energy |
| `progress` | Track with a fill from `fill`, text on top | Progress, EXP, HP |
| `title`, `text`, `label` | Large bold title, body text, small uppercase caption | Headings, descriptions, section captions |
| `image` | Striped placeholder with an icon | Art, characters, previews |
| `avatar` | Round portrait frame | Player profile |
| `tab` | Icon over a caption; `selected` highlights it | Bottom or side navigation |
| `bar` | Full-width strip | Top and bottom bars behind tabs |
| `badge`, `slot`, `divider` | Red count, empty dashed slot, thin line | Notices, empty inventory slots, separators |

Icons, from Lucide: settings, coins, gem, zap, heart, star, store, shopping-cart, house, play, pause, trophy, medal, crown, gift, package, backpack, user, circle-user, users, lock, x, arrow-left, chevron-left, chevron-right, plus, mail, bell, calendar, clock, timer, hourglass, map, flag, sword, swords, shield, hammer, wrench, key, scroll, book-open, list-checks, ticket, rotate-ccw, refresh-cw, tv, ban, volume-2, music, globe, info, circle-help, check, thumbs-up, message-circle, share-2, sparkles, flame, target, award, castle, car, puzzle, gamepad-2, rocket, image, search, menu, sliders-horizontal, and more in `assets/wire_icons.json`. Short aliases also work: coin, energy, close, back, shop, profile, inventory, mission, ranking, daily, spin, sound, language, ads, no_ads, chest, battle, reward.

## Mockup copy

Use these rules for demo concepts, revisions and assembled mockups. Keep the layout and required features from the wireframe. Choose the final copy separately.

- Prefer illustrations, icons and numbers when they communicate the feature. Show currency with its icon and balance, and progress with a bar and a value. Drop duplicate captions, explanatory sentences and descriptions the player can infer from the UI.
- Keep short English labels on primary action buttons such as `Play` and `Building`, even when the button has an icon.
- Keep short English names beneath the icons for navigation tabs such as `Shop`, `Home` and `Ranking`, for IAP offers in the left column such as `Starter Pack`, and for features in the right column such as `Daily`, `Spin` and `Missions`.
- Keep other text when the player needs it to identify an item or understand an action. Before sharing a concept or mockup, check that each required feature is still recognizable and each required label is readable.

## Layout guide for rearranging

Use this to judge your own work, and adapt it to the game's genre and the user's references.

- Give each screen one obvious main action, and make it the largest and strongest in color.
- Keep related items together. Align to a shared grid with a few consistent gaps, and use the same size for items of the same rank.
- On phones, put frequent actions within thumb reach at the lower corners. Put status at the top and infrequent menus away from the thumbs. Avoid covering the center of a gameplay view.
- Keep tappable items at least about 7 percent of the screen's short side, and clear of edges and notches.
- Leave breathing room rather than filling every space, and move secondary actions into a menu when a screen is crowded.
- Keep text short and readable. Add a dark plate or outline when it sits on busy art.
- Take colors from the kit's palette. Group by tone, and keep the same surface treatment across all controls of one rank, so the screen reads as one set. Reserve the strongest accent for the main action.
- Follow the visual weight of the tone you chose. Light, translucent controls and heavy dark panels are different decisions, and mixing them looks wrong even if every color is on the palette.

The `mockup` command warns about small tap targets, items too near the edge or off screen, and edges that almost align. It cannot judge beauty, so always view the result.

## Notes

- Show a progress bar with its track as one item and its fill on top with `fill`, sized slightly inside the track.
- Use the bare button sprite such as `btn_yellow` for normal and press feedback. Use an existing `_pressed` sprite when reproducing a legacy layout that specifies it, and `_disabled` to show a disabled button.
- A missing element draws as a red `MISSING` box and exits with status 2.
- Unknown keys are rejected, so a typo cannot silently change the layout.
