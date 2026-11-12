# Planning and prompts

## Element catalog

Include only the screens requested. **Base** parts are shared by every screen. The **screen-specific minimum** is what a screen must have of its own, so it does not end up as a plain panel with text. Take the exact list from the screen's concept, and add to it, not below it.

| Screen | Base parts it uses | Screen-specific minimum |
|---|---|---|
| Main menu | primary and secondary buttons, panel | title plate or logo, icon buttons for settings, sound and profile, a decorative frame or ribbon |
| Popup | popup panel, buttons | header ribbon, close button, divider, an icon or illustration for its message |
| Shop | panel, buy button, currency icons | tabs, item card frame, price tag, sale or rarity badge, item art, a currency plate with a plus button |
| Inventory | panel, buttons | item slot empty and selected, rarity frames, tabs, scrollbar, item art |
| HUD | bars, icon buttons | avatar frame, counter plates, pause button, action buttons, quick slots |
| Settings | panel, buttons, slider track and fill | an icon per row, slider knob, toggle on and off, row plate, close button, section tabs when there are more than about five rows |
| Results | panel, buttons | stars empty and filled, result ribbon, reward slots, item art |

A screen with only text labels where an icon would do is unfinished. In settings, every row gets an icon; in a shop, every item gets art and a price tag.

## Prompt template for a screen concept

Use this for the initial demo and each later screen concept. Use the approved anchor as a style reference when available.

```text
Use case: stylized-concept
Asset type: game UI screen concept, used as the design target for one screen
Input images: <wireframe for layout and required features, if supplied; style references for materials, palette, borders, lighting and level of detail>
Primary request: the <screen> screen of <game>, <orientation>, showing <functions of the screen>
Must include: <screen-specific minimum from the catalog, plus what the brief adds>
UI copy: Render only these exact English strings: <primary button labels, navigation captions, left-column IAP names, right-column feature names, and other essential text and values from the mockup copy rules>. Use illustrations, icons and numbers to communicate the other features.
Style/medium: <style guide summary>
Composition/framing: full screen, front-on, following the wireframe layout when supplied
Scene relationships: <target character pose, scale and visible body extent; intentional frame/counter/panel occlusion; support surfaces for scene props>. Match the target demo's composition; no exposed torso cuts or unintentionally floating scene objects.
Background: <approved source and visual direction>. For Home, show a crisp game scene with suitable props, a UI-kit background, or an abstract graphic backdrop. Use blur and dimming only on the parent screen behind a popup or overlay panel.
Avoid: duplicate labels, wireframe explanations, one plain panel holding only text and buttons, watermarks
```

## Sheet limits

For extracting or expanding a scene from a demo, use the dedicated prompt and measured canvas plan in [Background separation and multisize](backgrounds.md). This produces only the background plate and separately planned foreground assets. Continue assembling UI mockups from real sprites.

Actual generated dimensions vary. Plan sheet density conservatively and measure each returned asset against its largest placement; a requested resolution is not proof of native detail. Reduce items per sheet or render a hero asset individually when needed.

- Large panels and popups: 1 to 2 per sheet.
- Buttons, plates and cards: 4 to 6 per sheet.
- Bars and sliders: 4 to 6 per sheet, drawn long and horizontal.
- Icons: at most 9 per sheet. Use 4 for hero icons.

Keep one family in a sheet, because shared lighting and scale are the main defense against style drift.

## Prompt template for a component sheet

This template is for new component production. For extraction or quality restoration of an approved demo, use an edit prompt that locks its shape, proportions, volume, material, rim, bevel, palette, lighting and reflection geometry. Character edits must also preserve identity, expression, hair, clothes, pose and crop from the target demo, rather than locking an unsuitable reused sprite. Specify enough body extent for the target layout and its intended occlusion; extend hidden anatomy when needed without changing the approved visible appearance. Follow [scene composition and asset fit](mockup.md#scene-composition-and-asset-fit). Explicitly exclude accidental color/opacity mottling on uniform surfaces, while retaining intended texture. Follow [sprite fidelity and effect calibration](sprite-quality.md); a prompt requesting smoothness is not a quality check.

For intentional title/sign/logo lettering, use the exact English copy and preserve the reference's letterforms, line breaks, material, shadow/relief and shaped highlights following [typography](fonts.md). Produce a clean composed lettering PNG at usable resolution when that is the faithful representation. The generic no-text rule below applies to reusable body sheets, not these approved lettering assets. A named font in a generation prompt is a visual reference unless the actual font file is used to render the glyphs.

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

The no-external-shadow constraint is suitable for a body-only working image whose effects will be rebuilt. It is not permission to remove the reference's intended effects from the final sprite. Reconstruct and match their strength, softness and extent, then compose them with the body into one final PNG unless separate effect files were requested.

If the output has no real transparency, use this instead and pick a key color absent from the art, usually magenta and green for pink or purple art:

```text
Scene/backdrop: perfectly flat solid #FF00FF background, one uniform color edge to edge, no gradient, no texture, no shadow on the background
Constraints: never use the background color or anything close to it inside the elements
```

## Additions by family

- **Stretchable panels, buttons, plates:** Put stretch-safe detail at the borders when the approved design allows it. Preserve its dimensional gradients and reflections. Choose a safe stretch axis, fixed aspect ratio or another rendering approach when required; never flatten the reference's face or remove its gloss just to make 9-slice easier.
- **Buttons:** draw the normal state. The script derives disabled sprites. Use the normal sprite for press feedback in the game.
- **Bars:** draw the track and fill separately on the same sheet, with the same height and a plain horizontal middle section.
- **Icons:** use consistent visual weight, outline and lighting. Draw one straight base pose per icon and reuse it for directional variants that can be obtained by flipping or rotating it.

## Common failures

| Symptom | Fix |
|---|---|
| Parts of one element are cut apart | Raise `--gap`, or ask for a tighter single shape |
| Neighbors merge | Regenerate with wider gaps and fewer items |
| Style drifts between sheets | Re-attach the anchor, restate the style guide, reduce items per sheet |
| Colored fringe on edges | Regenerate with a key color further from the art |
