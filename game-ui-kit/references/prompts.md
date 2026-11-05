# Planning and prompts

## Element catalog

Include only families the requested screens use.

| Screen | Typical elements |
|---|---|
| Main menu | primary and secondary buttons, icon buttons, title plate, settings, sound and profile icons |
| Popup | popup panel, header ribbon, close button, confirm and cancel buttons, divider |
| Shop | item card, price tag, currency icons, tabs, sale badge, buy button |
| Inventory | item slot empty and selected, rarity frames, tabs, scrollbar |
| HUD | health, energy and progress bars as separate track and fill, avatar frame, counter plate, pause button |
| Settings | toggle on and off, slider track, fill and knob, checkbox, list row |
| Results | star empty and filled, result panel, reward slot, ribbon |

## Sheet limits

A generated image is only about 1024 to 1536 px on its long side, so items per sheet sets the final sprite size.

- Large panels and popups: 1 to 2 per sheet.
- Buttons, plates and cards: 4 to 6 per sheet.
- Bars and sliders: 4 to 6 per sheet, drawn long and horizontal.
- Icons: at most 9 per sheet. Use 4 for hero icons.

Keep one family in a sheet, because shared lighting and scale are the main defense against style drift.

## Prompt template for a component sheet

```text
Use case: stylized-concept
Asset type: game UI component sheet to be cut into separate sprites
Input images: Image 1: style reference, match its materials, palette, border treatment and lighting; do not copy its layout
Primary request: <count> separate <family> elements, arranged in a grid of <rows> rows and <columns> columns, in this exact reading order: <element list>
Style/medium: <style guide summary>
Composition/framing: flat front-on orthographic view; every element fully inside the frame; wide empty gaps between elements, at least 8 percent of the image width; no element touches another or the image edge
Scene/backdrop: transparent background
Constraints: no text, letters or numbers; no scene, no mockup, no drop shadow extending beyond the element; consistent scale
Avoid: painted checkerboard pattern, background gradient, floor shadow, watermark, overlap
```

If the output has no real transparency, use this instead and pick a key color absent from the art, usually magenta and green for pink or purple art:

```text
Scene/backdrop: perfectly flat solid #FF00FF background, one uniform color edge to edge, no gradient, no texture, no shadow on the background
Constraints: never use the background color or anything close to it inside the elements
```

## Additions by family

- **Stretchable panels, buttons, plates:** "decorations only at corners and edges; plain flat center with no texture, pattern or gradient across the width, so that it can be 9-sliced."
- **Buttons:** draw only the normal state. The script derives pressed and disabled.
- **Bars:** "track and fill as separate elements, same height, plain horizontal middle section."
- **Icons:** "same visual weight, same outline and lighting, centered, each fills about the same area."

## Common failures

| Symptom | Fix |
|---|---|
| Parts of one element are cut apart | Raise `--gap`, or ask for a tighter single shape |
| Neighbors merge | Regenerate with wider gaps and fewer items |
| Style drifts between sheets | Re-attach the anchor, restate the style guide, reduce items per sheet |
| Colored fringe on edges | Regenerate with a key color further from the art |
