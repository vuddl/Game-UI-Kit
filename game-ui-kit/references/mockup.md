# Mockup layout format

One file per screen at `ui_art/<kit>/mockups/<screen>.json`, or `<screen>__v1.json`, `<screen>__v2.json` for variants. Items draw in list order, so later items sit on top.

```json
{
  "size": [1080, 1920],
  "background": "#1E2A44",
  "reference": "style/references/shop.png",
  "items": [
    {"element": "panels/shop_panel", "x": 540, "y": 960, "w": 980, "h": 1400, "anchor": "center"},
    {"text": "Shop", "x": 540, "y": 330, "w": 700, "h": 90, "anchor": "center", "text_size": 64},
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
| `font` | Actual selected font file, relative to the kit or absolute. Bind it explicitly after visual matching. The first-font/system fallback is a technical fallback, not a style choice; see [typography](fonts.md). |

## Item keys

| Key | Meaning |
|---|---|
| `element` | Element name from the manifest. An item needs `element`, `text`, or both. |
| `text` | Ordinary sample copy, centered by visible glyph bounds in the item's content box and shrunk to fit width and height. Use a separate text item for a surface whose usable face differs from its full image box. Decorated lettering may instead be an imported PNG `element`. |
| `x`, `y` | Required. Position of the `anchor` point on screen. |
| `w`, `h` | Size. Both set a box. One keeps the sprite's proportions. Neither uses its native size. |
| `anchor` | `top_left` by default, or `top`, `top_right`, `left`, `center`, `right`, `bottom_left`, `bottom`, `bottom_right`. |
| `mode` | `auto` by default: 9-slice if borders are ready, otherwise fit inside the box without distortion. Also `nine`, `fit`, `stretch`. |
| `border_scale` | 9-slice corner size. By default corners shrink with the sprite and never grow, so set this only to override that, such as 2 when the screen resolution is far above the sprite's. |
| `fill` | From 0 to 1, for progress bars. `w` is the full width, the bar shortens from the right, and its round ends are kept. |
| `opacity` | From 0 to 1, for overlays and dimmed backdrops. |
| `text_color`, `text_size`, `text_stroke` | Text color, pixel size and optional outline width. Stroke is not shadow and must not be enabled unless it matches the reference. The basic renderer has no arbitrary text-FX schema; use faithful artwork/native target effects where required. |
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

Apply [reference-based typography](fonts.md) to representation, font choice, effects and optical placement. When a title has a decorative top bulge or outer shadow, define the lower main face as a separate label box instead of centering in the complete sprite. Keep the exact English label for lettering artwork in notes/`label`, without a duplicate drawn `text` item.

- Prefer illustrations, icons and numbers when they communicate the feature. Show currency with its icon and balance, and progress with a bar and a value. Drop duplicate captions, explanatory sentences and descriptions the player can infer from the UI.
- Keep short English labels on primary action buttons such as `Play` and `Building`, even when the button has an icon.
- Keep short English names beneath the icons for navigation tabs such as `Shop`, `Home` and `Ranking`, for IAP offers in the left column such as `Starter Pack`, and for features in the right column such as `Daily`, `Spin` and `Missions`.
- Keep other text when the player needs it to identify an item or understand an action. Before sharing a concept or mockup, check that each required feature is still recognizable and each required label is readable.

## Scene composition and asset fit

Apply to concepts, asset selection and assembled mockups, including `keep` layouts. Use the supplied mockup designated as the demo/layout target or the approved screen concept as the composition standard; a style-only reference does not override the chosen layout.

- **Compare the actual scene.** Check character pose, viewing angle, expression, scale, position, crop and occlusion order, plus background framing, props and their spatial relationships. Reuse one or two shared backgrounds/characters when they fit; do not treat that count as a cap or accept a match based only on theme or character identity. Create a screen-specific variant or regenerate the relevant art when reuse would compromise the demo, preserving identity and art direction and respecting the authorized generation scope/count.
- **Resolve body cuts intentionally.** A bust or half-body character needs an intentional portrait frame, viewport-edge crop or foreground occluder such as the demo's counter/panel. The occluder must actually cover the cut in the final composite. If the layout exposes more of the body, use or generate artwork with enough anatomy for that area. A torso ending in open scenery with an unexplained gap below it is a fault. A full body is not required when the reference calls for a framed or occluded portrait.
- **Preserve the target layout when repairing.** Prefer a suitable asset, body extension or correct layer order to forcing an incompatible sprite into place. Do not add arbitrary UI/props or move/enlarge the main panel solely to hide a cut when that departs from the demo. Make layout corrections only when they preserve the intended design or the user authorized rearranging; report material changes.
- **Judge scene and UI roles.** Props belonging to the scenery need plausible support, perspective, scale, lighting and contact/shadow relationships for the art style. A mixer intended to stand on a counter should not appear suspended above it. UI illustrations, framed portraits and intentionally floating magical objects can follow their own visual treatment when that role is clear from the demo; do not impose physical grounding on every icon.
- **Show the best intended state.** Choose the background and character variants that work together on this screen. Avoid unexplained empty gaps, awkward tangencies, accidental intersections, hidden focal details and attractive individual assets that form an incoherent whole. Preserve intentional negative space and reference occlusion rather than filling every gap.

Before delivery, view the full assembled screen beside its target at the same displayed size, then inspect joins and crop edges at full resolution. Check: does any body cut remain exposed, do scene props have the intended support, does each overlap make sense, and does the whole composition match the demo? Repeat on the required size/variant previews after repairs. Script PASS and asset-level QA do not answer these questions. Fix faults within the authorized scope and existing retry limits; otherwise report what remains unresolved rather than calling the screen finished. Record composition findings with the existing screen/background review notes, including why a new variant was needed when applicable.

## Layout guide for rearranging

Use this to judge your own work, and adapt it to the game's genre and the user's references.

- Give each screen one obvious main action, and make it the largest and strongest in color.
- Keep related items together. Align to a shared grid with a few consistent gaps, and use the same size for items of the same rank.
- On phones, put frequent actions within thumb reach at the lower corners. Put status at the top and infrequent menus away from the thumbs. Avoid covering the center of a gameplay view.
- Keep tappable items at least about 7 percent of the screen's short side, and clear of edges and notches.
- Leave breathing room rather than filling every space, and move secondary actions into a menu when a screen is crowded.
- Keep text short and readable. For a supplied design, preserve its original readability treatment: do not replace its shadow with a generic outline. For a new design, choose a treatment consistent with the approved art direction.
- Take colors from the kit's palette. Group by tone, and keep the same surface treatment across all controls of one rank, so the screen reads as one set. Reserve the strongest accent for the main action.
- Follow the visual weight of the tone you chose. Light, translucent controls and heavy dark panels are different decisions, and mixing them looks wrong even if every color is on the palette.

The `mockup` command warns about small tap targets, items too near the edge or off screen, and edges that almost align. It cannot judge beauty, so always view the result.

## Notes

- Show a progress bar with its track as one item and its fill on top with `fill`, sized slightly inside the track.
- Use the bare button sprite such as `btn_yellow` for normal and press feedback. Use an existing `_pressed` sprite when reproducing a legacy layout that specifies it, and `_disabled` to show a disabled button.
- A missing element draws as a red `MISSING` box and exits with status 2.
- Unknown keys are rejected, so a typo cannot silently change the layout.
