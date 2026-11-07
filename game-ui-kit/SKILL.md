---
name: game-ui-kit
description: Generate game UI wireframes, visual mockups and design files through five commands, $setup, $wireframe, $mockup, $reset and $info, asking the user through browser forms. Builds a consistent set of UI artwork (buttons with states, panels, popups, bars, frames, icons) as named transparent PNGs with 9-slice data, from a text brief, references or an existing UI kit, assembles mockups from the sprites, and exports layered PSD, PNG and a Unity assembly JSON. Use when the user types $setup, $wireframe, $mockup, $reset or $info, or asks for a game UI kit, wireframe, mockup or PSD. Does not build screens, prefabs or scenes in a game engine.
---

# Game UI Kit

Produce finished UI artwork with the built-in `image_gen` tool from the `imagegen` skill. It runs on the user's signed-in Codex account. Never use the `image_gen.py` CLI, an `OPENAI_API_KEY` or any paid service; if the built-in tool is unavailable or the plan limit is reached, stop and tell the user. Scripts handle cutting, naming, 9-slice and checks, so never hand-crop sheets or edit `manifest.json` by hand.

**Always reply to the user in Vietnamese,** including results, reports, choices and errors, whatever language the command or the scripts use. Keep commands, file paths, element names and in-game text as they are; in-game text follows the Text rule in Mockup.

Run scripts with `py -3` on Windows and `python3` elsewhere. They need Pillow and numpy. `<skill>` below is this skill's folder.

## Output

```text
ui_art/<kit_name>/
  briefs/     form answers: setup.json, wireframe/<screen>.json, mockup/<screen>.json, */full.json, export.json
  inputs/     files the user attached in the forms
  style/      style_anchor.png, style_guide.md, references/, concepts/
  sheets/     <sheet>.png and <sheet>.txt (element names, reading order)
  elements/   <family>/<name>.png   the sprites
  mockups/    <screen>__v1.json layouts: hidden working data, never shown as a result
  preview/    wireframes/, mockups/, contact_sheet.png, compare.png, flow.png
  demo/       index.html, the clickable prototype
  export/     psd/, png/, unity/, export_report.json
  .gui/       command state, kept by the scripts
  manifest.json and *_report.json
```

Copy every kept image out of `$CODEX_HOME/generated_images/` into the kit. Never change the user's original files.

## Commands

The user drives everything with five commands:

| Command | What it does |
|---|---|
| `$setup` | Asks the setup form: orientation or size, game type, gameplay. Every other command uses it. |
| `$wireframe` | Makes wireframe images, screen by screen or all at once. |
| `$mockup` | Makes the UI visual mockups, then exports the design files. |
| `$reset` | Throws away what the current command has made and starts it again. |
| `$info` | Shows everything saved so far: the setup, each screen's answers, results, exports and where the current command stands. Changes nothing. |

**Before anything else, run `state.py begin`** with the command's name, and act on what it prints:

```bash
py -3 <skill>/scripts/state.py ui_art/<kit> begin wireframe
```

| Prints | Do |
|---|---|
| `NEEDS_SETUP` | Do nothing else. Tell the user to run `$setup` first, in one line. |
| `START` | Start the command from its first step. |
| `RESUME` | The command was left unfinished for another one. Say so and carry on from its `step`. |
| `CONTINUE` | The same command is still running, so typing it again changes nothing. Carry on from its `step`. |

- **The latest command wins.** When the user types another command while one is unfinished, drop the old one at once, with no question and no wrap-up, and start the new one. The old one's work stays on disk.
- **Record progress** after each step with `state.py ui_art/<kit> step "<what was just done>"`, and run `state.py ui_art/<kit> done` when the command finishes.
- **`$reset`:** run `state.py ui_art/<kit> reset`. It deletes every file the current command created, its form answers and attachments included, and restores the text files it changed. Resetting `$setup` also deletes the setup, which blocks the other commands until `$setup` runs again. Report the counts it prints, then start the same command again from its first step.

- **`$info`** only reports, so it never runs `state.py begin`, never changes the current command and never resets anything. Run `state.py ui_art/<kit> summary` and present it in Vietnamese, in this order, skipping empty parts:
  1. **Setup:** kit name, size and orientation (dọc or ngang), game type, gameplay. Without a setup, say only to run `$setup`.
  2. **Đang làm:** the current command and its step, or that none is running, plus commands left unfinished.
  3. **Wireframe:** each screen with its function, filled areas, options count and prototype choice; screens from the full form; the image paths; the prototype path.
  4. **Mockup:** each screen with its source (UI kit and file count, references and file count, or colors, theme and UI style), background choice and note, and options count; screens from the full form; the image paths.
  5. **Export:** formats, layouts and file paths.
  6. The number of attached files kept in `inputs/`.
  End with one line on what to run next. After `$info`, carry on with the current command only when the user asks.

**Which kit.** `$setup` for a new game creates `ui_art/<game_slug>/`, named after the project folder unless the user named the game, and writes that name to `ui_art/.active`. Every other command uses the kit named in `ui_art/.active`. If that file is missing and several kits have `briefs/setup.json`, ask which one as a choice, then write it.

## Asking the user

**Forms** hold every question the flows below list. Open one with `ask.py`; never type those questions in chat:

```bash
py -3 <skill>/scripts/ask.py <form> ui_art/<kit> --out briefs/<file>.json
```

`<form>` is `setup`, `wireframe`, `full`, `mockup` or `export`, from `<skill>/forms/`. The script serves the form on localhost, opens the browser and prints `FORM_URL <url>`. Give the user that link in one line in case no browser opened. It waits until the user presses Hoàn thành, then prints one JSON line with `"status": "SUBMITTED"` and the answers, which it also saved to `--out`. The form fills in earlier answers from `--out`, so asking again lets the user edit them.

- Attached files are saved in `inputs/` and listed with their paths and notes in the answers. Use those paths, and view the images before using them. Files no answer refers to any more are deleted, so nothing piles up. A ZIP is unpacked; PSD files are kept as they are.
- If the command is cut off while waiting, use `--detach`, which opens the form and returns at once, then run `ask.py ui_art/<kit> --wait` until it prints `SUBMITTED`.
- `TIMEOUT` means nothing was saved: ask the user whether to open the form again.
- If the form cannot be served or opened at all, say why, then ask its questions in chat as a numbered list, as the last resort.

**Short questions in between,** such as the choices after showing a result, use the `request_user_input_async` tool when it is listed: one to three questions, each with short options, the recommended one first. It returns at once, so end the turn after calling it and act on the reply when it arrives. In Plan mode, use `request_user_input` instead. Without either tool, ask in one short message with numbered options the user can answer with a number. Never ask a form's questions this way.

## $setup

1. `state.py begin setup`, creating the kit as Which kit says.
2. Open the `setup` form with `--out briefs/setup.json`. The script turns the answer into `size` and `orientation`; a custom size counts as portrait when it is taller than wide.
3. Confirm in one line: kit, size, game type. Then `state.py done`.

Every layout uses the setup's `size`. The game type's description in [references/catalog.md](references/catalog.md) and the gameplay feed the tone and the layouts.

## $wireframe

Wireframes are gray boxes: no image generation and no art.

1. **Form for one screen.** Open the `wireframe` form with `--out briefs/wireframe/_new.json`. Rename the file to `briefs/wireframe/<screen>.json`, using its `screen`, replacing any earlier one.
2. **Draw it.** Write `options` layouts as `mockups/<screen>__v1.json`, `__v2` and so on, as Wireframe layouts describes, then run `uikit.py wireframe ui_art/<kit> --screen <screen>`. View each image in `preview/wireframes/` and show them. Make the options genuinely different and say in one line how.
3. **Ask, as a choice:**
   - **Sửa chữa tiếp:** the user describes the changes in chat. Change the layouts, draw and show again, then ask this again.
   - **Làm full màn:** step 4.
   - **Tiếp tục:** ask "Đã xong hết các màn chưa?" with **Xong rồi** and **Làm màn tiếp**. Xong rồi goes to step 5; Làm màn tiếp goes back to step 1.
4. **All the other screens at once.** Open the `full` form with `--out briefs/wireframe/full.json`. Draw every screen it picks with the first screen's setup, its options count included, using each screen's note and reference files and the shared request and files. Then step 5.
5. **Result.** Show every wireframe image and list their paths in `preview/wireframes/`. That is the whole result: no layout JSON is shown or delivered. If any screen's form said yes to a prototype, run `uikit.py flow ui_art/<kit> --wireframe --start <first screen>` and give the path of `demo/index.html`. Then `state.py done`.

### Wireframe layouts

Write layouts as [references/mockup.md](references/mockup.md) describes, at the setup's `size`, from the screen's function and its areas in the form: portrait Top, Middle, Bottom, or landscape Top, Left, Right, Bottom, used as `group` names. An empty area is yours to decide. List every button that changes screen with `goto`, so the prototype links work. Elements that do not exist yet are fine here. Follow the per-screen minimum in [references/prompts.md](references/prompts.md), so each screen shows what it is for.

## $mockup

1. **Form for one screen.** Open the `mockup` form with `--out briefs/mockup/_new.json`, then rename it to `briefs/mockup/<screen>.json`. It answers the screen, the wireframe files, the UI kit or references or art style, the background and the options count.
2. **Prepare.** Pick the role from the answers, as Choose the role says, and follow it until the sprites the screen needs exist. Before generating images, say the count and ask, as a choice, whether to go ahead.
3. **Build the screen.** Start from the wireframe the user attached. When it is one of this kit's `preview/wireframes/` images, start from its layout in `mockups/`; otherwise view the image, set it as the layout's `reference` and measure from it in `keep` mode. Write `options` layouts as `mockups/<screen>__v1.json` and so on, replacing that screen's wireframe layouts. Give the screen the background the form chose, as Backgrounds and art describes, and render it as Mockup describes. Show `preview/mockups/<screen>__v*.png`.
4. **Ask, as a choice:** **Sửa chữa tiếp**, **Làm full màn** or **Tiếp tục**, exactly as `$wireframe` step 3. Làm màn tiếp opens the `mockup` form again for the next screen, which asks everything again; use its new answers for that screen.
5. **All the other screens at once.** Open the `full` form with `--out briefs/mockup/full.json`. Build every screen it picks with the first screen's setup: its kit or style, its background choice and its options count. Use the screen's wireframe in `mockups/` when one exists, otherwise lay it out yourself, with each screen's note and reference files and the shared request.
6. **Result.** Show every mockup image in `preview/mockups/` with its path.
7. **Ask, as a choice, "Export không?"**
   - **Có:** step 8.
   - **Không:** ask "Sửa tiếp không?". If yes, the user describes the changes in chat; make them, show the result as in step 6, then ask "Export không?" again. If no, `state.py done`.
8. **Export.** Open the `export` form with `--out briefs/export.json`. Its answer gives `formats`, `psd`, `png` or both, and `layouts`, such as `home__v2`. Run, with one `--layout` per chosen layout:

```bash
py -3 <skill>/scripts/uikit.py psd ui_art/<kit> --layout home__v2 --background image --art image --force
```
```bash
py -3 <skill>/scripts/uikit.py export ui_art/<kit> --layout home__v2 --png-only --force
```
```bash
py -3 <skill>/scripts/uikit.py unity ui_art/<kit> --layout home__v2 --force
```

   Run `psd` only for `psd` and `export --png-only` only for `png`. Always run `unity`: `export/unity/<layout>.json` is the guide for assembling the screen in Unity. Report as Export describes, then `state.py done`.

## Choose the role

The `$mockup` form decides it: **A** when the user gave a UI kit, **B** when not.

### Role A: a UI kit is provided

Import the kit as Existing kit describes, then build the screens from it, adding only what it lacks:

- **Use the kit first.** For every slot on a screen, pick the kit element that fits its role best, and use the kit to the fullest. Create a new element only when no kit element suits the slot, not merely because a closer match could be drawn. Be flexible, though: the kit rarely covers every case, and a forced misfit is worse than a new element. List each new element with the slot it fills and why no kit element fits, and agree the list and image count before generating.
- **Keep kit names.** Import kit sprites with their original file names recorded, as Existing kit describes. Never set a layout item's `name` for a kit sprite. The PSD and Unity exports then name its layer by the user's own file name, with the same name on every use, so exporting layers from the PSD maps back to one resource instead of duplicates.
- **Every screen gets its own parts.** Check each screen against the per-screen minimum in [references/prompts.md](references/prompts.md). When the kit lacks a screen's specific parts, create them rather than filling the screen with the kit's generic panel and buttons.
- **New elements match the kit.** Use 2 to 4 kit sprites of the same family as the style reference, put the result in the matching family folder, such as a new button in `buttons/`, and name it by the naming rule in Export step 3. Only new elements get new names.
- The kit's own description in the form tells you what it is for and how to use it.

### Role B: no UI kit

1. **Starting point,** from the form:
   - **References:** use every file given, with its note deciding whether it is a reference for **layout** or **art style**, art style when it does not say. Give each the matching role in the Brief.
   - **Description:** use the colors, bright or dark theme, the chosen UI style and its description from [references/catalog.md](references/catalog.md), and the notes. Put them into the style guide and every prompt.
2. **Demo.** Generate the demo screen as in step 2, Style anchor, and let the user confirm it. Once confirmed, it is the anchor for the art style of every other screen. Save it as `style/style_anchor.png`, and add it as the screen's `reference`, measuring the mockup from it in `keep` mode so the confirmed screen keeps its proportions.
3. **Screen concepts.** Generate one concept per other screen type, in the demo's style, as Style anchor describes. Each shows what that screen needs beyond the shared parts.
4. **Two layers of components.** Build the base set first, exactly as [references/ui_kit_standard.md](references/ui_kit_standard.md) lists it: buttons in 6 colors plus special buttons, popup, font, title frames in 6 colors, background and pattern, the common icons, coin and gem in 5 tiers, common shapes, palette, reward frames and loading bars, with the names it gives. Draw the shapes with `shapes` rather than `image_gen`. Use and reuse the base set on every screen. Then build each screen's specific parts from its concept, such as tabs, item cards and price tags for a shop, or row icons and toggles for settings. Do not limit other screens to what the demo screen showed, which makes every screen look the same. Keep the base small and avoid near-duplicates, but never drop a screen's specific parts to save resources. Tell the user the image count per screen.

## Backgrounds and art

The form's background answer decides the source:

- **Provided:** use the user's files as the backgrounds, one per screen where they say which; set each as the layout's `background`.
- **From the kit:** use the kit's own backgrounds and patterns. Generate one in the game's art style only for a screen the kit cannot cover, and say so first.
- **Generate:** create new backgrounds in the art style, following the rules below.

The form's background note applies to all of these. Then:

- **Every screen has a background,** never a flat placeholder color.
  - **HUD:** generate a gameplay scene image that fits the game's art style, and put it under the HUD.
  - **Popup:** use the screen that opens it, blurred and dimmed. Render that screen first, then:

```bash
py -3 <skill>/scripts/uikit.py backdrop ui_art/<kit> <parent_screen>
```

  This writes `elements/backgrounds/bg_blur_<parent_screen>.png`. Set it as the popup layout's `background`, and rebuild it with `--force` when the parent screen changes.
- **Characters and items:** use them from the kit when it has them. Otherwise generate them to fit the game's art style, as `characters/` and `items/` elements. Show an item with its art, not with text or long descriptions.
- Generated backgrounds, scenes, characters and items are elements like any other, made with `image_gen` and listed with their image count before generating. Mark them `"role": "art"` in layouts. This is not drawing the mockup itself, which stays forbidden.

## Existing kit

The kit's files are in `inputs/` after the form, a ZIP already unpacked.

1. **Sheets:** copy each into `sheets/`, write its `.txt` names by viewing it, then slice as in step 4. If the sheet has a painted background or touching elements that the script rejects, report this rather than regenerating, because regenerating would replace the user's art.
2. **Loose sprites:** preview the names, because file names become element names. The original file name is also recorded, and exports name the sprite's layer by it, so renaming here never changes what the user's own files are called. Give button base names no state suffix, such as `btn_yellow`, so states work, using `--map` to rename:

```bash
py -3 <skill>/scripts/uikit.py import ui_art/<kit> "<kit folder>" --prefix buttons
```

Import each family into its own prefix, or use `--map` with lines of `relative/file.png = buttons/btn_yellow`. The files are copied unchanged. PSD, JPG and other formats are skipped and counted, so ask for PNG exports of those if needed.

3. View the kit, list which elements it lacks for the requested screens, and agree the list and image count with the user. Copy 2 to 4 representative sprites or screens into `style/references/`, write `style/style_guide.md` from what you see, and use these as the style anchor in step 3.

## 1. Brief

Everything comes from the forms: the setup, each screen's form and the `full` form. Do not ask again for what they answered. Label each attached image as **style reference** or **edit target**, and view local files first so the tool can see them. Give each reference one or more roles, and say them back to the user:

| Role | Decides | Stored in |
|---|---|---|
| **style** | Line work, shapes and materials | `style/references/` |
| **layout** | Positions and sizes | a layout's `reference` |
| **function** | Which controls must exist | `style/function_reference/` |

**Decide the tone yourself** before generating or laying out anything, unless the form's description set it. A reference is evidence, not the default. Weigh:

- **The game:** its genre, audience and mood, and the colors of its scene. UI must stay readable over that scene and feel part of the same world.
- **The references:** any existing UI's colors and surface treatment, and how well they suit this game.
- **Any kit art being reused:** new art must still sit beside it as one set.

Then use whichever fits best: the game's world, a reference, or a palette you compose from several. Decide the surface treatment too (opaque, translucent or outlined), since a palette alone does not capture it. Record the source and reason in `style/style_guide.md`, and tell the user in one or two lines what you chose and why.

Record the decision so everything stays consistent. Sample an image, using regions to keep out what you do not want, or give composed colors:

```bash
py -3 <skill>/scripts/uikit.py palette ui_art/<kit> <image> --region 0,0,240,120 --region 700,0,864,300
```
```bash
py -3 <skill>/scripts/uikit.py palette ui_art/<kit> --hex "#112233,#445566"
```

View `preview/palette.png`, and use tighter regions if it picked up colors you did not intend. Use only these colors in sheet prompts, layout backgrounds and text. Once sprites exist, change the palette only when the tone is deliberately changed, because existing sprites will not follow it and must be regenerated.

When extending a kit the user owns or says is licensed for this, match it closely. Otherwise, match the general art direction of a third-party kit without reproducing its elements one for one. If the user wants an exact copy of a purchased kit, say that its license decides this.

Plan the element list using [references/prompts.md](references/prompts.md) and name every new element by [references/ui_kit_standard.md](references/ui_kit_standard.md), split it into sheets, then tell the user the plan and the number of images it will generate. Plan it in two layers:

- **Base:** shared by every screen, such as the font, main buttons, panel, bars and frames. Keep this layer small and reuse it everywhere.
- **Screen-specific:** for each screen, the parts that show what the screen is for, taken from its screen concept and the per-screen minimum in [references/prompts.md](references/prompts.md). Every screen gets its own, so no screen is only a base panel, a button and text.

Keeping resources few applies to the base layer and to near-duplicates, never to the screen-specific layer. Reuse a screen-specific part on another screen only when it does the same job there, such as one close button for every popup.

## 2. Style anchor

Generate 1 to 3 concepts of the most representative screen. Without references, offer distinct directions. With references, stay close to them.

**Let the user choose, as a choice,** before generating any sheets, because every later image depends on it and uses their plan quota. Then save the choice as `style/style_anchor.png` and write `style/style_guide.md` with the palette, materials, corner shape, border treatment, lighting direction and icon treatment.

**Screen concepts.** The anchor fixes the style, not the content of other screens. A screen built only from the anchor screen's parts comes out as one plain panel, one button and text. So after the anchor is chosen, generate one concept for each other screen type, such as shop, settings, inventory or results, attaching the anchor as the style reference and using the concept template in [references/prompts.md](references/prompts.md). Screens of one type, such as two popups, share one concept. Say the image count first and show the concepts together. Save them as `style/concepts/<screen>.png` and set each as its layout's `reference`, so the mockup is checked against it in `<screen>_vs_reference.png`. The mockup reports `DETAIL_GAP` when it is much plainer than its concept; fix that before showing the screen.

Skip screen concepts only in Role A when the kit already covers a screen's specific parts, or when the user declines them.

## 3. Component sheets

Generate one `image_gen` call per sheet using the templates in [references/prompts.md](references/prompts.md), attaching the style anchor as a style reference every time. Save each as `sheets/<sheet>.png`.

Write `sheets/<sheet>.txt` with one element name per line, left to right and top to bottom, such as `buttons/btn_yellow`. Names use lowercase letters, digits and underscores, with `/` for folders.

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
py -3 <skill>/scripts/uikit.py nineslice ui_art/<kit> --match "popups/*" --match "buttons/btn_*"
```
```bash
py -3 <skill>/scripts/uikit.py nineslice ui_art/<kit> --match "bars/*" --axis horizontal
```
```bash
py -3 <skill>/scripts/uikit.py states ui_art/<kit> --match "buttons/btn_*"
```

Prefer derived states, because separately generated states rarely line up pixel for pixel. Generate a state with AI only when it needs a different drawing, such as a locked state with a padlock.

## Compare with references

Run this whenever new art exists and references exist, including after **the first sheet and before generating the rest**, so style drift costs one image instead of a whole kit:

```bash
py -3 <skill>/scripts/uikit.py compare ui_art/<kit>
```

It compares each new element with the recorded `style/palette.json`, or without one, with `style/style_anchor.png`, `style/references/` and any imported sprites, on palette fit, lightness and saturation, then writes `compare_report.json` and `preview/compare.png`, which shows references and palette beside the elements with flagged ones in red. Derived states and disabled elements are skipped. Add `--ref <image>` for another reference and `--match "icons/*"` to narrow it.

The numbers are only a screening aid and cannot judge shape, border style, material or lighting. **Always view `preview/compare.png`** and judge those yourself. A flag can be correct art, such as a red danger button in a kit with no red, so explain such cases rather than regenerating. A clean result does not prove the style matches.

## Mockup

Build mockups from the kit's real sprites, so the user can judge how the set works together. Run 9-slice first, so panels and buttons stretch correctly.

**Layout.** A screen with a wireframe, a layout reference or a concept uses `keep` against it: preserve its positions and sizes, only fixing real faults such as overlaps and cut-off items, and report each change. Measure every part a concept shows, decorations included, and give each its own element, so the mockup reproduces the concept rather than a sparser version of it. With none of these, or when the user says `rearrange`, decide the layout yourself following the guide in [references/mockup.md](references/mockup.md). Make options genuinely different, and explain each in one line.

**Count.** The form's options count is the number of layouts per screen. Tell the user the total before rendering, which `--plan` prints:

```bash
py -3 <skill>/scripts/uikit.py mockup ui_art/<kit> --plan
```
```bash
py -3 <skill>/scripts/uikit.py mockup ui_art/<kit> --screen <screen>
```

When there is a reference, view it, measure positions in its pixels, and set `reference`. Convert a reference of another size with `resize-layout`, which scales without distortion and reports empty margins; tell the user about them.

**Text.** Write in-game text in English unless the user names another language or the reference's text is in one. This is separate from the language you reply in. Add a label only where the meaning is not already clear, as the guide in [references/mockup.md](references/mockup.md) explains.

**Font.** Use the kit's font. If there is none, pick one following [references/fonts.md](references/fonts.md) before rendering, and report which. A `no font in the kit` warning means this step was missed.

**Richness.** The `mockup` and `qa` commands warn with `PLAIN_SCREEN` when a screen has fewer than 3 elements of its own, or shows more text than art, and `mockup` warns with `DETAIL_GAP` when a screen is much plainer than its concept. Treat that warning as a real fault: add the screen's specific parts from its concept rather than accepting a plain panel with text. The one exception is screens of one type, such as two popups, which may share all their parts; say so instead.

View each image in `preview/mockups/`, plus `<screen>_variants.png` and `<screen>_vs_reference.png` when present. Fix crowding, overlaps, wrong sizes and script warnings by editing the layout, which costs no quota, and render again. If a sprite does not fit its role, say so and offer to replace it. Check stretched sprites closely, especially at small sizes. If one looks bad, adjust `border_scale` or the size, draw bars with `fill`, and report what cannot be fixed by layout.

Never use `image_gen` to draw or polish a mockup, because a painted screen would hide how the real sprites look. Generate only the sprites the user agreed to; report each `MISSING_ELEMENT` otherwise. Give every screen its background as Backgrounds and art describes.

## 5. Check

```bash
py -3 <skill>/scripts/uikit.py qa ui_art/<kit>
```

Run this before showing a `$mockup` result. View `preview/contact_sheet.png`, `preview/compare.png`, `preview/mockups/` and the images in `preview/nineslice/`. Fix what the reports and your own eyes find, regenerating a given sheet at most twice. After that, stop and report the problem instead of spending more of the user's quota.

A `needs_review` 9-slice means no stretchable band was found. Regenerate that element with a plainer center, or tell the user it needs manual border work. Never report it as ready. A large-border warning means the corners take most of the sprite, so it only looks right near its original size. Keep it at that size or regenerate it with smaller corners.

## Export

Runs from `$mockup` step 8, on the layouts the export form chose.

**1. Backgrounds and art stay images** by default: `--background image --art image` keeps image backgrounds, characters, environments and other illustration as image layers. Redraw them as shapes only when the user asks in chat, with `--background redraw` or `--art redraw`. Mark such items `"role": "art"` in the layouts, and UI that a name might mislead `"role": "ui"`.

**2. Name layers.** A sprite imported from the user's kit is named by its original file name, the same on every use, and stays an image layer holding the user's file, so the user's own layer export does not duplicate resources. Never override that with `name`. Pass `--redraw-kit` only if the user asks for kit sprites as shapes too. Name everything else, which is what you created, by [references/ui_kit_standard.md](references/ui_kit_standard.md): `<function>_<description>[_<color>][_<screen>]` with its prefixes, such as `btn_yellow`, `title_red`, `set_coin_2`, `icon_settings`, `bg_main`. Without a `name`, one comes from the element, so review those. Use `group` for screen regions such as `hud_top_left`.

**3. PSD.** `psd` has Photoshop build `export/psd/<layout>.psd`, and opens only its own document if Photoshop is already running. It needs Photoshop on this machine. Otherwise it leaves `export/psd/<layout>.jsx`, which the user runs from File > Scripts > Browse on a machine that has it.

- **Hierarchy:** anything visually inside a sprite is grouped under that sprite's group, as parent and child, at any depth.
- **Shapes:** each UI sprite is redrawn as stacked vector shapes, and scored against its source. Those within the limit stay shapes; stretched ones keep their corners.
- **Images:** a sprite too detailed to redraw accurately stays a smart object holding the full-size source, placed before scaling, and repeats share one smart object. A source that had to be enlarged is reported.
- **Text:** real text layers. A font that is not installed falls back to Arial and is reported, so ask the user to install it.

Improve important simple sprites by hand when worthwhile, using `--match` and `--force` with `vectorize` to retry, and view the check image at `export/psd/assets/<layout>_check.png`.

**4. PNG.** `export --png-only` writes the flat screen to `export/png/<layout>.png`.

**5. Unity.** `unity` writes `export/unity/<layout>.json` with the same hierarchy, and each node's anchor, position relative to its parent, size, sprite, 9-slice, text, font and links. It does not build anything in Unity, and anchors are inferred from position, so say they may need adjusting.

**6. Report honestly** from `export/psd_report.json`: how many sprites are shapes, how many stayed images and why, live text count, missing fonts, and the difference from the mockup. Shapes are traced flat colors, so soft gradients become bands, and they are not a designer's hand-built vectors. Never call the file fully vector if anything stayed an image. Finish with the paths of every PSD, PNG and Unity file, the number of images generated, and every remaining warning. State clearly that mockups and PSD files are not screens built in the engine.
