# Reference-based typography

Use for font selection, English localization, decorative lettering, text FX and placement in concepts, sprites, mockups and exports. Preserve the approved design's typography as carefully as its other artwork. Choosing a font and choosing whether to deliver lettering as an image are separate decisions.

## Choose text or artwork by role

| Role | Preferred treatment |
|---|---|
| Ordinary labels, descriptions, changing values and localized UI copy | Use the matching font, with editable/native text when the target supports its required appearance. |
| Display lettering on titles, signs, logos or emblems with distinctive relief, shaped highlights, extrusion, warping or a curved baseline | Prioritize faithful English artwork and export a transparent PNG with its text FX already composed. Do not reduce it to plain live text just because it contains letters. |

Keep a native/editable source when available or specifically requested, but do not let a live-text preference override an approved decorated appearance. In a requested PSD, embed decorative lettering as a full-resolution Smart Object when that is the faithful representation; ordinary copy remains live text. A single finished lettering PNG may contain several internal text/effect layers in its working source.

Reuse the underlying button/title surface independently when appropriate. Place the lettering PNG as an `element`, with an English `label` if useful for the flow; do not also render the same `text` over it. Mark it `role: "art"` for PSD artwork routing. Match its native detail to the largest actual placement and preserve antialiased edges and complete effects.

## Select a font from the reference

1. Respect an explicitly required font. If the user merely supplies a kit/font collection, assess which files fit each role rather than choosing the first file available.
2. Inspect the actual demo lettering: family/style, glyph construction, width, weight, x-height, case, roundness, terminals, slant, spacing and line rhythm. Distinguish branding, titles, buttons, navigation, body copy and numbers when their designs differ.
3. Compare plausible fonts using representative words/glyphs from the demo at matched visible size, initially without FX. Search supplied/local fonts and then reputable font sources when needed. Generic genre categories are discovery aids, not evidence of a match. Do not default to Lilita One or repeat one font across unrelated roles.
4. Select the closest available match and the appropriate actual weight/style. Record the family, file, weight and variable axes where relevant, role and reason for substitution in the style guide or reconstruction notes. A visually close substitute is not a confirmed identification of the original font.
5. Render with the actual selected font file and inspect the result in context. A font name in an image-generation prompt does not prove that the generator used that font. If decorated artwork is generated rather than rendered from a font, report its appearance as a recreation and any named font as a style reference.

Reuse a compact role-based set where it fits the design; do not enforce a one-font or two-font ceiling at the expense of fidelity. The approved Lobster Two/Baloo 2/Nunito combination is an example for one bakery reference, not a new default for every game.

Store actual chosen `.ttf`/`.otf` files under `ui_art/<kit>/fonts/`, with available licensing information. Search the kit's other asset folders too. If a named font is missing from the helper's download catalog, obtain it from its official source or use the user's supplied file; the catalog is not the universe of allowed fonts. Check glyph coverage and the real weight rendered. For a variable font, a filename alone does not select Bold/ExtraBold: use supported axes or a fixed instance as appropriate to the renderer.

Bind each supported font explicitly rather than relying on alphabetical order in `fonts/`. The basic layout renderer supports one layout-level `font`; it does not support an item-level `font` or arbitrary text-FX keys. Use an appropriate explicit layout font for its live labels. For a different static role or unsupported decorative FX, render/import the correct lettering PNG, or finish native text/effects in the selected Photoshop. Preserve genuinely dynamic copy in a target that supports its actual font binding and report preview/export limitations rather than silently substituting another face.

`uikit.py fonts <kit> --add "<catalog family>"` downloads a catalog font and license. `uikit.py fonts <kit>` checks glyph coverage for layout text; it does not certify font likeness, style, optical alignment or decorated lettering images. Bundle the actual fonts needed by the selected deliverables where permitted and verify that the final package contains them; do not claim an unbundled font was supplied.

## Reproduce the actual text effects

Read the reference before selecting an effect: distinguish cast/drop shadow, stroke, bevel, extrusion, inner lighting, gloss and glow. A shadow is not an outline. Match color, direction, offset, darkness/brightness, softness, spread and depth at the final displayed scale, following [effect calibration](sprite-quality.md). Preserve intentional shaped highlights and contour relief rather than simulating everything with an outline.

Do not turn on `text_stroke` as a universal legibility fix or use it to imitate a reference shadow. The basic renderer's stroke uses an automatic contrast color; use it only if that treatment actually matches. Unsupported shadow/relief/curved lettering must be rendered faithfully as artwork or native target effects, not replaced by the nearest available toggle.

Localize retained copy to English while preserving its meaning, hierarchy and visual character. Adjust font size, spacing and line breaks for the translated length. Do not stretch glyphs horizontally, choose a mismatched font just to fill a box, or add text/features absent from the design. Check exact spelling and remove old-letter ghosts after replacement.

## Align to the main visible face

Identify the usable content region on the displayed button/title/panel. Exclude transparent padding, outer shadows/glows, extrusion outside the face, decorative peaks, chef hats, icons and ornaments. A title with a raised top emblem uses its lower band for the label; navigation captions use their band below the icon. Decorations are not automatically part of the centering rectangle.

Transform that content region using the same placement, fit/letterbox offsets and stretch behavior as its surface. Do not blindly center in the source PNG or the full layout item box. For simple layout text, make a separate text-only item whose `x/y/w/h` describe this measured region; combine `element` and `text` in one box only when their valid content regions coincide. These are existing layout fields, not a new `content_rect` schema key.

Measure the **visible glyph ink** with the selected font, not its nominal line box, advance width or the whole lettering PNG canvas. Fit both width and height. Align the glyphs within the content region, keeping shadow/glow extents out of the alignment calculation; leave enough export padding for those effects afterward. For a cropped lettering PNG, retain the crop/ink offset so transparent margins cannot shift the label when assembling it.

Apply optical correction after geometric placement: inspect uppercase/lowercase balance, ascenders, descenders, baseline, line spacing, italic overhang, translated word length and nearby ornaments. If the source has a curved baseline, preserve the curve within the main band and supersample the transformation so it does not create stair steps. Do not curve plain labels merely because their containing image is curved.

## Review before delivery

Compare the assembled English result and the approved demo at the same visible size. Inspect the chosen font, weight, FX type/strength, line breaks and optical placement in the screen, then zoom in on contours and small labels. A glyph-coverage check or numerical centering pass cannot certify likeness or beauty.

Record the chosen fonts, source/substitute status, text-versus-PNG decisions, content regions/optical offsets and important FX choices in existing reconstruction/style notes. Export intended lettering PNGs as named, reusable image resources and verify them alongside the completed screens. Respect any requested sample-review scope before wider replacement.
