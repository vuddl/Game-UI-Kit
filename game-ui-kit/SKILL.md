---
name: game-ui-kit
description: Generate a complete, consistent set of game UI artwork (buttons with states, panels, popups, bars, frames, tabs, icons) as named transparent PNGs with 9-slice data, from a text brief or reference images, or cut, organize and extend an existing UI kit. Also compares results against references, proposes wireframes and a clickable flow demo, assembles mockups from the sprites, and exports layered PSD files. Use when the user wants a game UI kit, UI art pack, UI sprites, or a wireframe, mockup, flow demo or PSD built from them, or types /info, /wireframe, /mockup, /choose, /flow or /export with this skill. Does not build screens, prefabs or scenes in a game engine.
---

# Game UI Kit

Produce finished UI artwork with the built-in `image_gen` tool from the `imagegen` skill. It runs on the user's signed-in Codex account. Never use the `image_gen.py` CLI, an `OPENAI_API_KEY` or any paid service; if the built-in tool is unavailable or the plan limit is reached, stop and tell the user. Scripts handle cutting, naming, 9-slice and checks, so never hand-crop sheets or edit `manifest.json` by hand. Reply to the user in their language.

Run scripts with `py -3` on Windows and `python3` elsewhere. They need Pillow and numpy. `<skill>` below is this skill's folder.

## Output

```text
ui_art/<kit_name>/
  style/      style_anchor.png, style_guide.md, references/
  sheets/     <sheet>.png and <sheet>.txt (element names, reading order)
  elements/   <family>/<name>.png   the deliverable
  mockups/    <screen>.json or <screen>__v1.json layouts, chosen.json
  preview/    contact_sheet.png, compare.png, flow.png, mockups/, wireframes/, nineslice/, labeled sheets
  demo/       index.html, the clickable flow
  export/     psd/, png/, export_report.json
  manifest.json and *_report.json
```

Do not overwrite an existing kit. Use a new `kit_name` or add to the existing one. Copy every kept image out of `$CODEX_HOME/generated_images/` into the kit, and every reference into `style/references/`. Never change the user's original kit files.

## Commands

The user can type these after `$game-ui-kit`, in any language, or say the same thing in words. If there is more than one kit in `ui_art/`, ask which, unless it is obvious from the conversation.

| Command | What to do |
|---|---|
| `/info` | Run the `info` script and report the status and next step in plain words. Change nothing. |
| `/wireframe [x]` | Propose layouts as gray boxes and the flow between screens, `x` options per screen, default 1. See Wireframes and flow. |
| `/mockup [x] [keep\|rearrange]` | Build `x` mockups per screen from real sprites, default 1. See Mockup. |
| `/choose <screen> v<n>` | Record the approved variant with the `choose` script. |
| `/flow` | Draw the flow and build the clickable demo. See Wireframes and flow. |
| `/export [screen]` | Export approved screens. See Export. Only ever run on this command or when the user says the screens are final. |

None of these generate images, so they use no image quota. Report the number of mockups before and after rendering.

## Choose the mode

| What the user has | Mode | Steps |
|---|---|---|
| Nothing, or only images for inspiration | **New kit** | 1, Wireframes and flow, 2, 3, 4, Mockup, 5 |
| Kit sheets to cut, wanting nothing new | **Cut only** | Existing kit, then 4, 5. No image generation. Mockup only if asked |
| Loose sprites to organize, wanting nothing new | **Organize only** | Existing kit, then the 9-slice and states commands in 4, then 5. No image generation. Mockup only if asked |
| A kit, plus elements it lacks | **Extend** | Existing kit, then 1, Wireframes and flow, 3, 4, Mockup, 5. Skip step 2 |
| A finished kit, wanting to see it on a screen | **Mockup only** | Existing kit if not yet imported, then Mockup, 5. No image generation |

If the user attached a kit without saying which they want, ask once whether to only process it or also create missing elements, since only the latter uses quota. Do not generate images in the first two modes, even if something looks missing; list what is missing instead.

## Existing kit

1. **Sheets:** copy each into `sheets/`, write its `.txt` names by viewing it, then slice as in step 4. If the sheet has a painted background or touching elements that the script rejects, report this rather than regenerating, because regenerating would replace the user's art.
2. **Loose sprites:** preview the names, because file names become element names. Keep button base names ending in `_normal` so states work, using `--map` to rename:

```bash
py -3 <skill>/scripts/uikit.py import ui_art/<kit> "<kit folder>" --prefix buttons
```

Import each family into its own prefix, or use `--map` with lines of `relative/file.png = buttons/btn_primary_normal`. The files are copied unchanged. PSD, JPG and other formats are skipped and counted, so ask for PNG exports of those if needed.

3. **Extend only:** view the kit, list which elements it lacks for the requested screens, and agree the list and image count with the user. Copy 2 to 4 representative sprites or screens into `style/references/`, write `style/style_guide.md` from what you see, and use these as the style anchor in step 3.

## 1. Brief

Collect the game, its genre, platform and orientation, the screens needed, and any references. Ask only for what is missing and blocks the work, at most one short message. If screens are not named, default to main menu, popup, shop and HUD.

Label each input image as **style reference** or **edit target**. Load local files with `view_image` first so the tool can see them. When extending a kit the user owns or says is licensed for this, match it closely. Otherwise, match the general art direction of a third-party kit without reproducing its elements one for one. If the user wants an exact copy of a purchased kit, say that its license decides this.

Plan the element list using [references/prompts.md](references/prompts.md), split it into sheets, then tell the user the plan and the number of images it will generate. If wireframes come next, finalize the list after them, because they show which elements the screens need.

## Wireframes and flow

Propose how the screens are laid out and connected before spending quota on art. Write layouts as described in [references/mockup.md](references/mockup.md), naming options `mockups/<screen>__v1.json`, `__v2` and so on. List every button that changes screen with `goto`. Elements that do not exist yet are fine here.

```bash
py -3 <skill>/scripts/uikit.py wireframe ui_art/<kit>
```
```bash
py -3 <skill>/scripts/uikit.py flow ui_art/<kit> --wireframe --start <first_screen>
```

`flow` writes `preview/flow.png` and a clickable `demo/index.html`, and reports broken links, unreachable screens and dead ends. Fix what is unintended. View the images, show them to the user, and name the option you recommend. Run `flow` again without `--wireframe` once mockups exist, so the demo shows the real art.

## 2. Style anchor

Generate 1 to 3 concepts of the most representative screen. Without references, offer distinct directions. With references, stay close to them.

**Stop and let the user choose** before generating any sheets, because every later image depends on this choice and uses their plan quota. Skip the stop only if the user asked for no check-ins. Then save the choice as `style/style_anchor.png` and write `style/style_guide.md` with the palette, materials, corner shape, border treatment, lighting direction and icon treatment.

## 3. Component sheets

Generate one `image_gen` call per sheet using the templates in [references/prompts.md](references/prompts.md), attaching the style anchor as a style reference every time. Save each as `sheets/<sheet>.png`.

Write `sheets/<sheet>.txt` with one element name per line, left to right and top to bottom, such as `buttons/btn_primary_normal`. Names use lowercase letters, digits and underscores, with `/` for folders.

Check each sheet by eye before slicing. Regenerate it if elements overlap, contain text, drift from the anchor, or are missing.

## 4. Process

Slice each sheet:

```bash
py -3 <skill>/scripts/uikit.py slice ui_art/<kit> sheets/<sheet>.png
```

The script reads real alpha when present, otherwise it keys out a flat background. Handle its failures this way:

| Result | Action |
|---|---|
| `BACKGROUND_NOT_FLAT` | The sheet has a painted or fake checkerboard background. Regenerate on the flat key color. |
| `COUNT_MISMATCH` | Open the labeled sheet in `preview/`. Fix `--gap` if parts split or merged, fix the `.txt` if the list is wrong, or regenerate. |

Suggest 9-slice for elements that stretch, then derive button states:

```bash
py -3 <skill>/scripts/uikit.py nineslice ui_art/<kit> --match "panels/*" --match "buttons/*_normal"
```
```bash
py -3 <skill>/scripts/uikit.py nineslice ui_art/<kit> --match "bars/*" --axis horizontal
```
```bash
py -3 <skill>/scripts/uikit.py states ui_art/<kit> --match "buttons/*_normal"
```

Prefer derived states, because separately generated states rarely line up pixel for pixel. Generate a state with AI only when it needs a different drawing, such as a locked state with a padlock.

## Compare with references

Run this whenever new art exists and references exist, including after **the first sheet and before generating the rest**, so style drift costs one image instead of a whole kit:

```bash
py -3 <skill>/scripts/uikit.py compare ui_art/<kit>
```

It compares each new element with `style/style_anchor.png`, `style/references/` and any imported sprites, on palette fit, lightness and saturation, then writes `compare_report.json` and `preview/compare.png`, which shows references and palette beside the elements with flagged ones in red. Derived states and disabled elements are skipped. Add `--ref <image>` for another reference and `--match "icons/*"` to narrow it.

The numbers are only a screening aid and cannot judge shape, border style, material or lighting. **Always view `preview/compare.png`** and judge those yourself. A flag can be correct art, such as a red danger button in a kit with no red, so explain such cases rather than regenerating. A clean result does not prove the style matches.

## Mockup

Build mockups from the kit's real sprites, so the user can judge how the set works together. Run 9-slice first, so panels and buttons stretch correctly.

**Layout decision.** A mockup either keeps the existing layout or rearranges it. Follow `keep` or `rearrange` if the user said so. Otherwise, when a reference layout exists, ask this one question before writing layouts. With no reference, use `rearrange`.

- **keep:** preserve the reference's positions and sizes. Only fix real faults, such as overlaps and cut-off items, and report each change. Extra variants differ only in spacing and scale.
- **rearrange:** decide the layout yourself to look good and play well, following the guide in [references/mockup.md](references/mockup.md). Make the variants genuinely different, and explain each in one line.

**Count.** `x` in `/mockup x` is the number of variants per screen, default 1. Tell the user the total before rendering, which `--plan` prints, and again afterwards:

```bash
py -3 <skill>/scripts/uikit.py mockup ui_art/<kit> --plan
```
```bash
py -3 <skill>/scripts/uikit.py mockup ui_art/<kit>
```

Name layouts `mockups/<screen>__v1.json` and so on, or `<screen>.json` when there is only one. When there is a reference, view it, measure positions in its pixels, set `size` to its size and set `reference`. Use short sample text in the user's language.

View each image in `preview/mockups/`, plus `<screen>_variants.png` and `<screen>_vs_reference.png` when present. Fix crowding, overlaps, wrong sizes and script warnings by editing the layout, which costs no quota, and render again. If a sprite does not fit its role, say so and offer to replace it. Check stretched sprites closely, especially at small sizes. If one looks bad, adjust `border_scale` or the size, draw bars with `fill`, and report what cannot be fixed by layout.

Never use `image_gen` to draw or polish a mockup, because a painted screen would hide how the real sprites look. Do not generate missing sprites unless the current mode and the user's approved plan include them; report each `MISSING_ELEMENT` instead. A kit with no background art gets a flat color, so say that the mockup shows sprites and layout rather than final screen art.

## 5. Check and deliver

```bash
py -3 <skill>/scripts/uikit.py qa ui_art/<kit>
```

View `preview/contact_sheet.png`, `preview/compare.png`, `preview/mockups/` and the images in `preview/nineslice/`. Fix what the reports and your own eyes find, regenerating a given sheet at most twice. After that, stop and report the problem instead of spending more of the user's quota.

A `needs_review` 9-slice means no stretchable band was found. Regenerate that element with a plainer center, or tell the user it needs manual border work. Never report it as ready. A large-border warning means the corners take most of the sprite, so it only looks right near its original size. Keep it at that size or regenerate it with smaller corners.

## Export

Run only on `/export` or when the user says the screens are final. If any screen has several variants and none is chosen, ask the user which, then record it:

```bash
py -3 <skill>/scripts/uikit.py choose ui_art/<kit> <screen> v2
```
```bash
py -3 <skill>/scripts/uikit.py export ui_art/<kit>
```

This writes `export/psd/<screen>.psd` and a flat `export/png/<screen>.png`. Each sprite and text is a named layer, items with the same `group` form a folder, and the reference is a hidden bottom layer. Use `group` in the layouts so folders follow screen regions. Tell the user that **text layers are pixels, not editable type**, and that stretched sprites are already drawn at their final size. Give `--force` only if the user asked to replace an export.

Finish with the kit path, element counts per family, the number of images generated, how the art compared with references, the number of mockups and their paths, any demo and export paths, and every remaining warning. State clearly that mockups and PSD files are not screens built in the engine.
