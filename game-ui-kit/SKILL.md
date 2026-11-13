---
name: game-ui-kit
description: Generate game UI wireframes, visual mockups and design files through six commands, $setup, $wireframe, $mockup, $export, $reset and $info, asking the user through browser forms. Builds a consistent set of UI artwork (buttons with states, panels, popups, bars, frames, icons) as named transparent PNGs with 9-slice data, from a text brief, references or an existing UI kit, assembles mockups from the sprites, and exports layered PSD, PNG and a Unity assembly JSON. Use when the user types $setup, $wireframe, $mockup, $export, $reset or $info, or asks for a game UI kit, wireframe, mockup or PSD. $export also accepts existing UI mockup images without setup or earlier commands. Does not build screens, prefabs or scenes in a game engine.
---

# Game UI Kit

Produce finished UI artwork with the built-in `image_gen` tool from the `imagegen` skill. It runs on the user's signed-in Codex account. Never use the `image_gen.py` CLI, an `OPENAI_API_KEY` or any paid service; if the built-in tool is unavailable or the plan limit is reached, stop and tell the user. Scripts handle cutting, naming, 9-slice and checks, so never hand-crop sheets or edit `manifest.json` by hand.

**Always reply to the user in Vietnamese,** including results, reports, choices and errors, whatever language the command or the scripts use. Keep commands, file paths and element names as they are.

**Use English for all visible UI copy** in generated wireframes, concepts, mockups and prototypes, including titles, labels, button text, captions, badges and status messages. Translate visible copy carried over from briefs, references or earlier layouts. Check the rendered output for English copy before showing it, including after revisions.

For font selection, lettering FX and placement, follow [reference-based typography](references/fonts.md). Choose fonts by role and likeness to the demo, preserve each actual effect, prioritize English PNG artwork for distinctive decorated titles/signs, and center visible glyphs within the main face rather than the full image or its shadows/decorations.

Run scripts with `py -3` on Windows and `python3` elsewhere. They need Pillow and numpy. `<skill>` below is this skill's folder.

For sprite production, extraction and quality repairs, follow [clean edges, material alpha and effect fidelity](references/sprite-quality.md). Improve usable resolution and smoothness while preserving the approved design, volume, bevels and shaped reflections. Preserve good antialiased contours; minimum extra feather is not a binary cut. Match shadow/FX strength, softness and spread to the demo, not a generic subtle preset. Separate effects internally and deliver one composed PNG per asset by default. Compare at the same visible size and on multiple backdrops before delivery.

## Output

```text
ui_art/<kit_name>/
  briefs/     form answers: setup.json, wireframe/<screen>.json, mockup/<screen>.json, */full.json, export.json
  inputs/     files the user attached in the forms
  style/      style_anchor.png, style_guide.md, references/, concepts/
  sheets/     <sheet>.png and <sheet>.txt (element names, reading order)
  elements/   <family>/<name>.png   the sprites
  mockups/    <screen>__v1.json layouts: hidden working data, never shown as a result
  preview/    wireframes/, mockups/, backgrounds/, contact_sheet.png, compare.png, flow.png
  demo/       index.html, the clickable prototype
  export/     delivery/ (selected files), psd/, png/, unity/, backgrounds/, *_report.json
  .gui/       command state, kept by the scripts
  manifest.json and *_report.json
```

Copy every kept image out of `$CODEX_HOME/generated_images/` into the kit. Never change the user's original files.

## Commands

The user drives everything with six commands:

| Command | What it does |
|---|---|
| `$setup` | Asks orientation or size, game type and gameplay. Required for `$wireframe` and `$mockup`; optional for `$export`. |
| `$wireframe` | Makes wireframe images, screen by screen or all at once. |
| `$mockup` | Makes and reviews screen demos in one approved style. Creates and assembles UI kit sprites only when requested, then optionally enters `$export`. |
| `$export` | Exports supplied mockup images or existing screens. Select UI kit with demos, component PSD, screen PSDs, Unity JSON and/or ZIP with report. Needs no setup or earlier command. |
| `$reset` | Throws away what the current command has made and starts it again. |
| `$info` | Shows everything saved so far: the setup, each screen's answers, results, exports and where the current command stands. Changes nothing. |

**Before anything else, run `state.py begin`** with the command's name, and act on what it prints:

```bash
py -3 <skill>/scripts/state.py ui_art/<kit> begin wireframe
```

| Prints | Do |
|---|---|
| `NEEDS_SETUP` | Applies only to `$wireframe` and `$mockup`. Tell the user to run `$setup` first. `$export` is exempt. |
| `START` | Start the command from its first step. |
| `RESUME` | The command was left unfinished for another one. Say so and carry on from its `step`. |
| `CONTINUE` | The same command is still running, so typing it again changes nothing. Carry on from its `step`. |

- **The latest command wins.** When the user types another command while one is unfinished, drop the old one at once, with no question and no wrap-up, and start the new one. The old one's work stays on disk.
- **Record progress** after each step with `state.py ui_art/<kit> step "<what was just done>"`, and run `state.py ui_art/<kit> done` when the command finishes.
- **`$reset`:** run `state.py ui_art/<kit> reset`. It deletes every file the current command created, its form answers and attachments included, and restores the text files it changed. Resetting `$setup` also deletes the setup, which blocks `$wireframe` and `$mockup` until `$setup` runs again; `$export` remains available. Report the counts it prints, then start the same command again from its first step.

- **`$info`** only reports, so it never runs `state.py begin`, never changes the current command and never resets anything. Run `state.py ui_art/<kit> summary` and present it in Vietnamese, in this order, skipping empty parts:
  1. **Setup:** kit name, size and orientation (dọc or ngang), game type, gameplay. Without a setup, report that it is absent and continue showing standalone export progress and results; do not block `$info`.
  2. **Đang làm:** the current command and its step, or that none is running, plus commands left unfinished.
  3. **Wireframe:** each screen with its function, filled areas, options count and prototype choice; screens from the full form with its per-screen options count and prototype choice; the image paths; the prototype path.
  4. **Mockup:** each screen with its source, background and options count; draft and approved demo paths per screen, the style anchor and whether sprite production was requested; assembled mockup paths when present. Keep demo approval distinct from sprite production.
  5. **Export:** source images and dimensions, selected formats, layouts, chosen Photoshop, actual delivery paths and remaining warnings.
  6. The number of attached files kept in `inputs/`.
  End with the relevant command suggestions below. After `$info`, carry on with the current command only when the user asks.

**Which kit.** `$setup` for a new game creates `ui_art/<game_slug>/`, named after the project folder unless the user named the game, and writes that name to `ui_art/.active`. `$export` may also create a kit and set `.active`, without making `briefs/setup.json`; reuse the active kit when it belongs to the requested game, otherwise use the user's game name or a new export-session folder. Other commands use `.active`. If it is missing, consider kits with a saved setup or an export brief/state; ask which one only when several match. Never require a setup merely to select an export session.

### Suggested next commands

After a command finishes, append **Lệnh tiếp theo** below the result in the final chat reply. Put each suggested command on its own bullet in the format `$tên_lệnh: mô tả ngắn` and list the most useful option first. Present suggestions for the user to invoke. If the user already chose the next command, proceed with that choice. Show suggestions after required forms and review choices are resolved.

| After | Suggested commands |
|---|---|
| `$setup` | `$wireframe: Tạo bố cục cho một hoặc nhiều màn.` `$mockup: Tạo demo giao diện từ ảnh hoặc link wireframe.` `$export: Xuất UI kit, PSD, JSON Unity hoặc ZIP nếu bạn đã có ảnh mockup.` |
| `$wireframe` | `$mockup: Thiết kế giao diện từ wireframe đã tạo.` `$wireframe: Tạo bố cục cho các màn còn lại.` |
| `$mockup` | Suggest `$mockup` for more screens or continued work from approved demos. Suggest `$export` when the user has an exportable screen or a mockup image to supply and has not just declined export. |
| `$export` | `$info: Xem các file đã xuất và tiến độ của kit.` Suggest `$setup` if the kit has no setup and the user wants to design new screens. |
| `$info` | Suggest resuming an unfinished command or use the latest completed stage above. With no setup, suggest `$setup` for starting a design or `$export` for a supplied mockup. |

`$reset` restarts the current command as described above. Use that command's suggestions once it finishes.

## Asking the user

**Forms** hold every question the flows below list. Open one with `ask.py`; never type those questions in chat:

```bash
py -3 <skill>/scripts/ask.py <form> ui_art/<kit> --out briefs/<file>.json
```

`<form>` is `setup`, `wireframe`, `full`, `mockup`, `revise` or `export`, from `<skill>/forms/`. The script starts the form server on its own, opens the browser, prints `FORM_URL <url>`, and then waits until the user presses Hoàn thành. Then it prints one JSON line with `"status": "SUBMITTED"` and the answers, which it also saved to `--out`. The form fills in earlier answers from `--out`, so asking again lets the user edit them.

**Stay in the turn while the form is open.** The user expects you to carry on by yourself the moment they press Hoàn thành, and once your turn ends nothing can wake you. So:

- Give the user the `FORM_URL` link in one short progress line, never as your final message. Never end the turn with "fill in the form and I'll wait" or similar.
- Keep the command running until it prints `SUBMITTED`. If the shell hands it back still running, keep polling that same session for more output. If it exits printing `WAITING`, run `ask.py ui_art/<kit> --wait` and keep waiting the same way. `still waiting for the form` lines are only a heartbeat.
- As soon as it prints `SUBMITTED`, go straight on with the next step of the command, in the same turn.
- Before opening a form, record the step as `waiting for form <form> --out <file>`, so a later turn knows a form is pending.
- **If the turn ended anyway,** the user's next message, whatever it says (such as "xong"), means: first run `ask.py ui_art/<kit> --wait --timeout 0`. `SUBMITTED` gives the answer, so carry on from there; `WAITING` means the form is still open, so give the link again and keep waiting. The server keeps an answer until `--wait` collects it.
- `TIMEOUT` means nothing was saved: ask the user whether to open the form again.
- If the form cannot be served or opened at all, say why, then ask its questions in chat as a numbered list, as the last resort.

Description and note fields place attachment thumbnails, text and a compact **+** control in the same box. Attach through the picker, drag and drop, or clipboard paste. Click a thumbnail to view the image or edit the attachment note where available. References are stored in `inputs/`. Existing reference areas can unpack ZIP files containing only supported artwork. The artwork pickers for wireframes, source mockups, UI kits and backgrounds accept PNG, JPG, WebP, PSD or ZIP and unpack supported artwork from ZIP files.

Read attachments from the saved `answers`, including references in nested options and per-file fields. A field's attachments are listed under `files` or `field_files.<field id>` alongside its value. View attached images before using them and read other files as relevant to their field. Files no saved answer refers to are deleted. In the wireframe form, `answers.function.files` can supply the entire screen description. Each region keeps its text in `answers.areas.value` and its references in `answers.areas.field_files.<region>`.

Click an attached image thumbnail to view the original image in a large overlay in the form. Close it with the close button, Escape or the overlay background; the form keeps its text, attachments and scroll position.

**Short questions in between,** such as the choices after showing a result, use the `request_user_input_async` tool when it is listed: one to three questions, each with short options, the recommended one first. It returns at once, so end the turn after calling it and act on the reply when it arrives. In Plan mode, use `request_user_input` instead. Without either tool, ask in one short message with numbered options the user can answer with a number. Never ask a form's questions this way.

**Revision prompts.** When the user chooses **Sửa demo**, **Sửa concept** or **Sửa chữa tiếp**, open `revise` directly for the current draft or versions. Collect the change request, reference images and per-image notes together in the form. Apply each image as a reference for the version it was attached to.

## $setup

1. `state.py begin setup`, creating the kit as Which kit says.
2. Open the `setup` form with `--out briefs/setup.json`. The script turns the answer into `size` and `orientation`; a custom size counts as portrait when it is taller than wide.
3. Run `state.py done`. Confirm the kit name, size and game type in the final reply and append the suggestions for `$setup`.

Wireframe and generated mockup layouts use the setup's `size`. Standalone export layouts use each supplied image's actual size and orientation. The game type's description in [references/catalog.md](references/catalog.md) and the gameplay feed the tone and the layouts. A game type the user typed under Lựa chọn khác has no catalog entry; its `game_type_description`, when given, takes that place.

## $wireframe

Wireframes are clean, readable screens drawn from the layout in a headless browser: rounded cards, icons, a clear type scale, real progress bars and tab bars, and real text. No image generation and no art. `uikit.py wireframe` draws them with Edge or Chrome; it prints `WARNING NO_BROWSER` and draws plain boxes when neither is found, so tell the user.

0. **Choose the scope immediately.** On a new wireframe run, offer the two choices from step 3b before opening a screen form. If the user already requested one screen or multiple screens, go directly to step 1 or step 4 respectively. Multiple screens need only `$setup`; no first wireframe, concept or art-style approval is required. On RESUME/CONTINUE, keep the saved scope and pending step.
1. **Form for one screen.** Open the `wireframe` form with `--out briefs/wireframe/_new.json`. Rename the file to `briefs/wireframe/<screen>.json`, using its `screen`, replacing any earlier one.
2. **Draw it.** Write `options` layouts as `mockups/<screen>__v1.json`, `__v2` and so on, as Wireframe layouts describes, then run `uikit.py wireframe ui_art/<kit> --screen <screen>`. View each image in `preview/wireframes/` and show them. Make the options genuinely different and say in one line how.
3. **Ask about revisions after showing the wireframes.** This applies to both single-screen and batch results, including after each revision. Record `waiting for wireframe revision choice` with `state.py step`, then open the interactive question **"Bạn có muốn chỉnh sửa tiếp không?"** with exactly **Có** and **Không**, using `request_user_input_async` when available. Follow Asking the user for the numbered-choice fallback when the tool is unavailable. Wait for the answer; do not finish the command or suggest `$mockup` while this choice is pending. If the user's current message already explicitly answers this revision question, act on that answer directly.
   - **Có:** open the revision form in step 3a.
   - **Không:** finalize in step 5.
3a. **Revise.** Open the `revise` form with `--out briefs/revise.json --kind wireframes --screens <screen>`, listing every screen just shown, comma-separated. It shows each version with its image; the user ticks the ones to change, writes the change for each, and may attach images with a note each, such as "nút bo tròn như ảnh này". Its record lists `versions`, each with `layout`, `change` and `files`, plus a `common` answer for all. View every attached image, change only the ticked layouts, draw and show them again, then ask step 3 again.
3b. **Choose the scope.** At the beginning of a wireframe run, or when the user explicitly asks to add more screens, ask "Bạn muốn làm tiếp theo cách nào?" with exactly these two choices. This scope menu does not replace the revision question after showing results.
   - **Làm nhiều màn · Ít chi tiết hơn** opens the batch form in step 4. Focus on each screen's core features and use shared patterns to keep the batch consistent.
   - **Làm 1 màn · Chi tiết hơn** opens the single-screen form in step 1. Give the next screen a dedicated pass on layout and details before showing it.
4. **Multiple screens.** Open the `full` form with `--out briefs/wireframe/full.json` while the current command is `wireframe`. It asks for screens, whether to create a flow prototype, and 1–5 options for each screen. Draw every selected screen at the size and orientation from `$setup`, using the batch brief's `options` count for each screen, its notes/reference images and the shared request/files. Do not inherit a previous single-screen count or require an existing wireframe. Make the options meaningfully different. View and show every screen's images, then go to the revision question in step 3; do not skip directly to completion or `$mockup`.
5. **Result, after the user declines further revisions.** List every wireframe image path in `preview/wireframes/`. No layout JSON is shown or delivered. For a batch, use its own `prototype` choice; for single-screen work, use the screen form's choice. If yes, only now add `goto` to buttons that change screen, run `uikit.py flow ui_art/<kit> --wireframe --start <first selected screen>` and give the path of `demo/index.html`. Include all selected screens in the prototype. The flow uses the chosen variant for each screen, or its first option if none was chosen; state which options the demo uses. Then run `state.py done` and append the suggestions for `$wireframe`.

### Wireframe layouts

Write layouts as [references/mockup.md](references/mockup.md) describes, at the setup's `size`, from the screen's function and its areas in the form: portrait Top, Middle, Bottom, or landscape Top, Left, Right, Bottom, used as `group` names. An empty area is yours to decide. Elements that do not exist yet are fine here. Follow the per-screen minimum in [references/prompts.md](references/prompts.md), so each screen shows what it is for.

- **Give every item its kind** with `wf`, and an `icon`, as the Wireframe items table in [references/mockup.md](references/mockup.md) lists, so it draws as a real control: currency as `pill` with `coins` or `gem`, the main action as `button_primary`, side features as `icon_button` with a short caption, a bottom `bar` with `tab` items and one `selected`, progress as `progress` with `fill`, art as `image`.
- **Real text.** Write the actual English titles, values, captions and button labels the player should see, such as "Play", "12,500" and "Progress 3 / 8". Reserve element names for the source layout.
- **Build a hierarchy:** one large `title`, small `label` captions above sections, values in bold, secondary lines in `text`. Use a few sizes consistently.
- **No flow text on the screen.** Never write a target such as "> shop" or "gem > shop" in a label. Add `goto` only when the applicable single-screen or batch form said yes to a prototype, in step 5; links show only in `demo/index.html` and `preview/flow.png`, never on the wireframe.

## $mockup

Demo design and sprite production are separate phases. **Chốt demo / Chốt concept approves only that image and its design. It never requests sprite creation, extraction, background production or assembly.** This also applies when resuming older briefs that already contain `approved_concept`. Continue with the demo action menu until the user explicitly requests **Tạo UI kit sprite**, or clearly asks for sprite production in chat. A request to continue demos, submit a form or approve a style does not start sprite production.

1. **Form.** Open the `mockup` form with `--out briefs/mockup/_new.json`. It records the wireframes, UI kit/references/art style, background and one demo count per screen (`options`, 1–5), used for both the first style demo and later screens. Do not ask for a separate concept/generation count. Each uploaded wireframe or link is one screen, listed in `screens` with its `label`, `note` and either `file` or `url`. The kit's existing wireframes come prefilled. Users can submit just links, or combine them with uploads.
   - Each linked wireframe has a URL and an optional description with inline image attachments. Open the URL with an available connector or browser and inspect the intended frame. Use the description and its images in that link entry's `field_files.note` under `answers.wireframe.value` to locate the frame or guide the layout. If you cannot open the link, tell the user and continue with the description or other references if they define the screen. Ask for an accessible link or an image if you still need the layout.
   - A screen with an empty `screen` has no name. Name it from its linked frame, description or images, and say which name you gave.
   - Use the submitted wireframe for each screen. If several versions of the same screen are listed, use the one the user explicitly confirmed when it is among those sources. Ask which one only if the choice is still ambiguous.
   - Rename the file to `briefs/mockup/<first screen>.json`. Start with one representative screen to establish the style; keep all other submitted screens queued for demos.
2. **First demo and style.** Use Role A or B as reference guidance, without entering component production. The submitted `options` authorizes that many initial complete demo images; with a supplied UI kit, attach representative kit art as style references. On `SUBMITTED`, state the count and generate the demo images in the same turn. Follow Style anchor to revise and approve the selected demo. Save the exact approved image and establish the style anchor. Reuse saved approvals on resume; ask about generation only when exceeding the authorized scope/count. In older briefs, the retired `concept_count` is historical data; do not use it as a second count or repeat already generated demos.
3. **Demo action menu.** After each demo approval, offer **Làm tiếp demo màn khác**, **Tạo UI kit sprite**, and **Dừng tại demo**. If the user's message already selects one, act on it directly.
   - **Làm tiếp demo màn khác:** step 4. Keep the first screen's approved style as the anchor.
   - **Tạo UI kit sprite:** step 5. This is the explicit production request.
   - **Dừng tại demo:** show approved demos and any remaining drafts, save progress, then `state.py done`. Preserve all demo approvals so a later request can resume them. Do not start production or automatically enter export.
4. **More screen demos.** Offer one screen or multiple screens. For queued screens, use their existing brief without asking again. Otherwise open `full` with `--out briefs/mockup/full.json` while the current command is `mockup`, allowing one or multiple screen selections with notes and references. Inherit the first brief's style, background instructions and `options` demo count; do not reopen style selection. Generate complete demo images using the approved anchor as a style reference and each screen's own wireframe/requirements. Review and approve each screen separately as Style anchor describes. A demo for another screen does not replace the first style anchor. Return to step 3 after review; approving one screen does not approve all other demos.
5. **Requested sprite production.** Record the explicit request and its screen scope in the demo register below. Use only demos already approved for those screens. If any requested screen still lacks approval, finish its demo review first. Plan shared and screen-specific assets from the exact approved demos, state the asset list and generation count, then follow Component sheets, Process and Backgrounds and art. Reuse existing kit sprites where they match. Approval to produce sprites for some screens does not automatically include future screens or revised demo versions.
6. **Assemble and compare.** Use each approved demo as its screen layout's `reference` in `keep` mode; preserve its composition, proportions, visual hierarchy, typography and details. Keep the original wireframe layout available. Assemble the real sprites into `mockups/<screen>__v*.json`, render `preview/mockups/<screen>__v*.png`, compare against the corresponding approved demo and complete QA. A painted demo is a design target; the assembled sprite mockup is the production result. Show both for review. **Sửa chữa tiếp** opens `revise --kind mockups`; apply production fixes against the approved demo. A requested design change returns that screen to demo review before rebuilding affected sprites.
7. **Ask, as a choice, "Export không?"**
   - **Có:** step 8.
   - **Không:** ask "Sửa tiếp không?". If yes, open the `revise` form as in `$wireframe` step 3a, with `--kind mockups`; make the changes, show the result as in step 6, then ask "Export không?" again. If no, `state.py done`.
8. **Export.** Use the same form, format choices and packaging as standalone `$export`. Finish the mockup command with `state.py done`, then `state.py begin export` on the same kit. Enter the flow below with existing screens as the source. Do not force Unity, PNG or a component PSD when it was not selected. Finish the export state when its selected outputs are delivered.

### Demo register and resume

Save `briefs/mockup/demos.json` with `style_anchor` (the first approved demo's kit-relative path), `screens` (a list of `{screen, label, drafts, approved_demo}`), and `sprite_production` (`requested: false` until an explicit request, then `requested: true` plus the exact `screens` and `approved_demos` paths requested). Keep each screen's current `approved_concept` in its mockup brief for compatibility; the register stores approvals for all screens even when a batch shares one brief. Record the current demo/review/production step with `state.py step`. On resume, read the register and briefs: missing production authorization means return to the demo menu, even if all demos are approved or old sprites exist. If a demo is revised, preserve the previous image and clear that screen's current approval until the new image is approved; the old production request does not cover the revision.

## $export

This is a standalone command. It requires neither `$setup` nor completed wireframes/mockups, and it does not run those commands as prerequisites.

1. Resolve or create the session as Which kit describes, then run `state.py ui_art/<kit> begin export`. Respect START/RESUME/CONTINUE and save steps normally.
2. For source images already attached in chat, preserve and prefill them with `delivery.py add-source ui_art/<kit> "<original file>"`, optionally `--screen <screen>`; it copies attachments and ZIP contents into `inputs/` without changing originals. Do not make the user attach them twice. If exporting existing screens, use those directly.
3. Record `waiting for form export --out briefs/export.json` and open the `export` form every time. Keep waiting until SUBMITTED. When no kit screens exist, the form uses supplied images automatically and hides the source question; when both sources are available, let the user choose. It supports multiple simultaneous output choices. PSD choices require an explicit local Photoshop selection; the form checks/configures script execution for that installation immediately and shows readiness or the one-time restart requirement before submission, as [Photoshop configuration](references/photoshop.md#configure-script-execution-in-the-export-form) describes. PNG/UI-kit or Unity-only requests do not require Photoshop configuration.
4. For supplied images, inspect each one, infer a useful screen name when blank, and update its source entry in the export brief. Run `delivery.py prepare ui_art/<kit>` to read each image's own dimensions and allocate layout names. Its NEEDS_RECONSTRUCTION status is a work step: proceed with separation and reconstruction as [Standalone export](references/export.md) describes. Do not create a setup, reinterpret the source as an unapproved style concept, or deliver a screenshot as extracted components.
5. Follow [Standalone export](references/export.md) for reconstruction, background multisize, selected PSD/Unity creation, dynamic Base organization, global resource deduplication and packaging. Existing kit exports enter the same work at validation/reuse, avoiding unnecessary regeneration.
6. Run the checks for the selected outputs, build the delivery and run `state.py done`. In the final reply, list actual files and remaining limits in Vietnamese, report image generation count, and append the suggestions for `$export`.

## Choose the role

The `$mockup` form decides it: **A** when the user gave a UI kit, **B** when not.

### Role A: a UI kit is provided

During demo design, use representative kit images as style references for the complete demos. After an explicit sprite-production request, import the kit as Existing kit describes and build the approved screens from it, adding only what it lacks:

- **Use the kit first.** For every slot on a screen, pick the kit element that fits its role best, and use the kit to the fullest. Create a new element only when no kit element suits the slot, not merely because a closer match could be drawn. Be flexible, though: the kit rarely covers every case, and a forced misfit is worse than a new element. List each new element with the slot it fills and why no kit element fits, and agree the list and image count before generating.
- **Keep kit names.** Import kit sprites with their original file names recorded, as Existing kit describes. Never set a layout item's `name` for a kit sprite. The PSD and Unity exports then name its layer by the user's own file name, with the same name on every use, so exporting layers from the PSD maps back to one resource instead of duplicates.
- **Every screen gets its own parts.** Check each screen against the per-screen minimum in [references/prompts.md](references/prompts.md). When the kit lacks a screen's specific parts, create them rather than filling the screen with the kit's generic panel and buttons.
- **New elements match the kit.** Use 2 to 4 kit sprites of the same family as the style reference, put the result in the matching family folder, such as a new button in `buttons/`, and name it by the naming rule in Export step 2. Only new elements get new names.
- The kit's own description in the form tells you what it is for and how to use it.

### Role B: no UI kit

1. **Starting point,** from the form:
   - **References:** use every file given, with its note deciding whether it is a reference for **layout** or **art style**, art style when it does not say. Give each the matching role in the Brief.
   - **Description:** use the colors, bright or dark theme, the chosen UI style and its description from [references/catalog.md](references/catalog.md), and the notes. A style typed under Lựa chọn khác uses its `ui_style_description` instead of a catalog entry. Put them into the style guide and every prompt.
   - **References with style answers:** with references, the colors, theme, UI style and notes are optional. What is left empty comes from the references; what is answered overrides them, such as a dark theme over a bright reference. Say in one line what you took from the references and what from the answers.
2. **First demo.** Generate and review the first demo screen as in Style anchor. Use its approved draft as the style anchor. For every later screen, inherit this style and save that screen's own approved demo as its visual `reference` for production in `keep` mode.
3. **More demos.** When the user chooses to continue, generate and review complete demos for the selected screens in the first demo's style. Each screen needs its own approval before production.
4. **Two layers of components, after the explicit sprite request.** Build the base set first, exactly as [references/ui_kit_standard.md](references/ui_kit_standard.md) lists it: buttons in 6 colors plus special buttons, popup, font, title frames in 6 colors, background and pattern, the common icons, coin and gem in 5 tiers, common shapes, palette, reward frames and loading bars, with the names it gives. Draw the shapes with `shapes` rather than `image_gen`. Use and reuse the base set on every screen. Then build each screen's specific parts from its approved demo, such as tabs, item cards and price tags for a shop, or row icons and toggles for settings. Do not limit other screens to what the first demo showed. Keep the base small and avoid near-duplicates, but never drop a screen's specific parts to save resources. Tell the user the image count per screen.

## Backgrounds and art

During demo review, inspect the background, UI and foreground composition without extracting or generating production assets. Once sprite production is explicitly requested, identify which pixels belong to the scene background, UI, characters, props or separate foreground layers, then follow [Background separation and multisize](references/backgrounds.md): remove baked UI, reconstruct hidden scenery, calculate outpainting from the target aspect range, protect the main subjects, and check both the clean background and the UI composite at those sizes. Apply this to supplied and generated demos, in either orientation. Standalone `$export` retains its independently authorized reconstruction workflow.

**Reuse is a preference, not a fixed asset limit.** One or two shared backgrounds or character images are useful when they fit the screens. Judge each against the supplied mockup or approved screen concept; matching the theme or character identity alone is insufficient. If the scene framing, pose, crop or occlusion cannot match with the existing art, plan a suitable variant or regenerate that background/character within the authorized scope and image count. Follow [scene composition and asset fit](references/mockup.md#scene-composition-and-asset-fit) before choosing assets and before delivery. Present each mockup in its best intended state with coherent scenery, subjects and UI.

The form's background answer decides the source:

- **Provided:** use the user's files, one per screen where they say which. A full mockup must first go through separation and reconstruction; an existing clean plate can go straight to multisize planning and checks.
- **Extract demo:** use the demo/reference already supplied, or the files on this option. Resolve its intended screen from the image and notes; ask only if multiple sources remain ambiguous. Preserve the scene identity while cleaning and extending the background.
- **From the kit:** use the kit's own backgrounds and patterns when their composition fits the target screen. A thematically similar background that cannot reproduce the demo's framing or support its subjects does not cover that screen; plan a matching variant or new background and state the image count before generating.
- **Generate:** create new backgrounds in the art style, following the rules below.

The form's background note applies to all of these. Then:

- **Multisize:** use the optional `background_targets` answer and any already supplied device requirements. Otherwise state the working range from `background.default_targets(setup_size)`: base size, 16:9, 20:9 and 4:3 in the setup's orientation. This is a stated test range, not universal device support. Create a profile in `briefs/backgrounds/`, link it with `background_profile` in each affected layout, and run `background.py check` with and without that layout's UI overlay. Show the background identification, clean expanded image and multisize board. Uniform cover must preserve the image proportions; export the full master, its actual dimensions and crop/alignment guidance for Unity. If a protected subject fails or UI hides it, adjust the extension or alignment, separate the subject, or propose variants for the affected aspect ranges. Recheck after background or UI changes.
- **Every screen has a background,** never a flat placeholder color.
  - **Home:** use a crisp scene with scenery and props that fit the game, a suitable background from the UI kit, or an abstract graphic backdrop without a specific setting. Compose the background with quieter areas behind UI controls.
  - **HUD:** generate a gameplay scene image that fits the game's art style, and put it under the HUD.
  - **Popup or overlay panel:** reserve backdrop blur and dimming for the parent screen visible behind a foreground overlay. Standalone screens use their own backgrounds at normal sharpness and brightness. Render the parent screen first and run:

```bash
py -3 <skill>/scripts/uikit.py backdrop ui_art/<kit> <parent_screen>
```

  This writes `elements/backgrounds/bg_blur_<parent_screen>.png`. Set it as the overlay layout's `background`, and rebuild it with `--force` when the parent screen changes.
- **Characters and items:** reuse kit art when its pose, perspective, scale, visible body extent and intended occlusion fit the target mockup. Otherwise plan a matching variant or new `characters/` or `items/` element while preserving the game's art style and character identity. Never leave a torso cut exposed in open scenery; use the reference's intentional framing/occlusion or artwork with enough body for the visible area. Show an item with its art, not with text or long descriptions.
- Production backgrounds, scenes, characters and items are elements like any other, made with `image_gen` after the production request and listed with their image count before generating. Mark them `"role": "art"` in layouts. Complete painted images are allowed for demo design; final production mockups are assembled from real sprites.

## Existing kit

The supplied UI kit artwork is in `inputs/` after the form, with supported assets from ZIP files already unpacked.

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

**Decide the tone yourself** before generating or laying out anything, unless the form's description set it. A reference is evidence, not the default.

This discretion applies to unspecified art direction. A supplied mockup used as the layout/demo target or an approved concept remains the composition standard; do not reinterpret it merely to accommodate shared assets.

Weigh:

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

After the explicit sprite-production request, plan the element list from all approved demos in scope using [references/prompts.md](references/prompts.md), name every new element by [references/ui_kit_standard.md](references/ui_kit_standard.md), split it into sheets, then tell the user the plan and image count. Plan it in two layers:

- **Base:** shared by every screen, such as the font, main buttons, panel, bars and frames. Keep this layer small and reuse it everywhere.
- **Screen-specific:** for each screen, the parts that show what the screen is for, taken from its screen concept and the per-screen minimum in [references/prompts.md](references/prompts.md). Every screen gets its own, so no screen is only a base panel, a button and text.

Keeping resources few applies to the base layer and to near-duplicates, never to the screen-specific layer. Reuse a screen-specific part on another screen only when it does the same job there, such as one close button for every popup.

## 2. Style anchor

Generate the approved number of concepts of the most representative screen using the [screen concept prompt](references/prompts.md). Use the confirmed wireframe for layout and required features. Select the English strings to keep using the [mockup copy rules](references/mockup.md#mockup-copy) and use the approved background source from Backgrounds and art. Include the selected strings and background treatment in every concept and revision prompt. Without style references, vary the visual direction. With style references, stay close to them.

1. **Select a draft.** Save the concept images in `style/concepts/` with distinct names such as `home__concept_1.png` and show them. If there is more than one, ask which to refine. With one concept, use it as the draft. Record the draft's path in the command step and enter review.
2. **Review the current draft.** Show its image and offer **Sửa demo** and **Chốt demo** (also accept the earlier labels **Sửa concept / Chốt concept**). On **Sửa demo**, open `revise` with `--kind concepts --screens <draft_stem> --out briefs/mockup/concept_revisions/<draft_stem>.json`. The form shows just that draft and collects changes and optional reference images. On `SUBMITTED`, view the reference images and apply the edits to the draft while keeping the confirmed wireframe layout. Save the revised image under a new name, record its path, show it, and repeat this review step.
3. **Finalize the demo only.** Record the exact approved image as the kit-relative `approved_concept` path in that screen's mockup brief and `approved_demo` in the demo register. For the first approved screen only, copy it to `style/style_anchor.png` and write `style/style_guide.md` with the palette, materials, corner shape, border treatment, lighting direction and icon treatment. Later screen demos use this anchor without replacing it. Return to the demo action menu; approval alone never starts sprite production. On resume, return to review if the current draft lacks approval; an anchor file alone does not establish approval or a production request.

**Screen demos.** When the user chooses to continue demos, generate only the selected screens, attaching the first approved anchor as a style reference and using [the screen concept prompt](references/prompts.md). The anchor fixes the style; each screen keeps its own content and layout. Save versioned images as `style/concepts/<screen>__concept_<n>.png`, show them, and review each screen separately. Reusing a screen pattern does not share approval between screens. After an explicit production request, use each exact approved demo as that screen's layout `reference` and compare the assembled result in `<screen>_vs_reference.png`; fix `DETAIL_GAP` before showing a finished sprite assembly.

An existing kit can supply the style and sprites, but each screen still needs an approved demo before assembly in this workflow. Standalone `$export` follows its own supplied-image workflow.

## 3. Component sheets

For either role, start generating, extracting or processing production sprites only after the user explicitly requests sprite production and the exact demos for the requested screens are approved. Check the demo register's production scope and approved image paths before starting. Follow the planned asset list and image count from the requested production step. An approved demo or style anchor alone is insufficient.

Generate one `image_gen` call per sheet using the templates in [references/prompts.md](references/prompts.md), attaching the style anchor as a style reference every time. Save each as `sheets/<sheet>.png`.

Plan the [base components](references/ui_kit_standard.md) before building screen-specific parts. Use one canonical, upright icon for any set of variants that can be flipped or rotated from the same artwork. List the base sprite once and reuse it with a transform in the game. Keep distinct art for different meanings or states. Put each loading bar fill and track on the same sheet so `slice` can align their canvases.

Write `sheets/<sheet>.txt` with one element name per line, left to right and top to bottom, such as `buttons/btn_yellow`. Names use lowercase letters, digits and underscores, with `/` for folders.

Check each sheet by eye before slicing. Regenerate it if elements overlap, contain unintended text, drift from the anchor, or are missing. Planned English lettering artwork is intentional; follow the typography rules rather than deleting or replacing it with generic text.

## 4. Process

Slice each sheet:

```bash
py -3 <skill>/scripts/uikit.py slice ui_art/<kit> sheets/<sheet>.png --canonical-icons
```

The script reads real alpha when present, otherwise it keys out a flat background. It trims sprites to their visible bounds and adds only the transparent padding needed for width and height to be multiples of four. It preserves the standard reward frame size and gives loading bar pairs on the same sheet a shared canvas. Use `--canonical-icons` for newly generated sheets and omit it when importing existing kit artwork. Handle its failures this way:

| Result | Action |
|---|---|
| `BACKGROUND_NOT_FLAT` | The sheet has a painted or fake checkerboard background. Regenerate on the flat key color. |
| `COUNT_MISMATCH` | Open the labeled sheet in `preview/`. Fix `--gap` if parts split or merged, fix the `.txt` if the list is wrong, or regenerate. |
| `DUPLICATE_ICON` | Keep the canonical icon in the plan and reuse it for the equivalent directions. |

Suggest 9-slice for elements that stretch, then derive disabled button sprites:

```bash
py -3 <skill>/scripts/uikit.py nineslice ui_art/<kit> --match "popups/*" --match "buttons/btn_*"
```
```bash
py -3 <skill>/scripts/uikit.py nineslice ui_art/<kit> --match "bars/*" --axis horizontal
```
```bash
py -3 <skill>/scripts/uikit.py states ui_art/<kit> --match "buttons/btn_*"
```

Use the normal button sprite for press feedback in the game. Generate a separate state only when it needs different artwork, such as a locked button with a padlock.

## Compare with references

During sprite production, run this whenever new production art and references exist, including after **the first sheet and before generating the rest**, so style drift costs one image instead of a whole kit:

```bash
py -3 <skill>/scripts/uikit.py compare ui_art/<kit>
```

It compares each new element with the recorded `style/palette.json`, or without one, with `style/style_anchor.png`, `style/references/` and any imported sprites, on palette fit, lightness and saturation, then writes `compare_report.json` and `preview/compare.png`, which shows references and palette beside the elements with flagged ones in red. Derived states and disabled elements are skipped. Add `--ref <image>` for another reference and `--match "icons/*"` to narrow it.

The numbers are only a screening aid and cannot judge shape, border style, material or lighting. **Always view `preview/compare.png`** and judge those yourself. A flag can be correct art, such as a red danger button in a kit with no red, so explain such cases rather than regenerating. A clean result does not prove the style matches.

## Mockup

Build mockups from the kit's real sprites, so the user can judge how the set works together. Run 9-slice first, so panels and buttons stretch correctly.

**Layout.** A screen with a wireframe, a layout reference or a concept uses `keep` against it. Preserve the positions and sizes of the feature groups and controls. The wireframe establishes the layout and required features. Choose how to depict each feature using the mockup copy rules. Measure the approved concept's visual details, including its decorations, and give each its own element. Fix issues such as overlaps and cut-off items and report layout changes. With no reference or when the user says `rearrange`, follow the guide in [references/mockup.md](references/mockup.md). Make options genuinely different, and explain each in one line.

**Count.** The form's options count is the number of layouts per screen. Tell the user the total before rendering, which `--plan` prints:

```bash
py -3 <skill>/scripts/uikit.py mockup ui_art/<kit> --plan
```
```bash
py -3 <skill>/scripts/uikit.py mockup ui_art/<kit> --screen <screen>
```

When there is a reference, view it, measure positions in its pixels, and set `reference`. Convert a reference of another size with `resize-layout`, which scales without distortion and reports empty margins; tell the user about them.

**Text.** Apply the [mockup copy rules](references/mockup.md#mockup-copy) and [typography rules](references/fonts.md) to the concept and assembled screen. Keep ordinary English copy editable where its appearance is supported; prioritize faithful English PNG artwork for decorated titles, signs and emblems. Do not impose live text on stylized lettering or render a duplicate label over its PNG. Match text FX and place the glyphs in the measured main face, excluding shadows and decorative peaks.

**Font.** Respect explicitly required fonts; otherwise compare kit/local/source candidates against each role in the approved demo following [references/fonts.md](references/fonts.md). Reuse a kit font when it fits, not merely because it exists or sorts first. Bind the actual selected file/weight, report close substitutions honestly and inspect them in the rendered screen. Do not default every role to Lilita One. A missing-font warning must be resolved or reported, and a successful glyph check alone does not establish a visual match.

**Richness.** The `mockup` and `qa` commands warn with `PLAIN_SCREEN` when a screen has fewer than 3 elements of its own, or shows more text than art, and `mockup` warns with `DETAIL_GAP` when a screen is much plainer than its concept. Treat that warning as a real fault: add the screen's specific parts from its concept rather than accepting a plain panel with text. The one exception is screens of one type, such as two popups, which may share all their parts; say so instead.

View each image in `preview/mockups/`, plus `<screen>_variants.png` and `<screen>_vs_reference.png` when present. Apply [scene composition and asset fit](references/mockup.md#scene-composition-and-asset-fit) to the full composite, not just individual sprites. Fix crowding, overlaps, wrong sizes and script warnings by editing the layout, which costs no quota, and render again. If a sprite cannot fit its role without distorting the target composition, replace or regenerate it within the approved scope/count; seek approval only for work beyond that authorization. Check stretched sprites closely, especially at small sizes. If one looks bad, adjust `border_scale` or the size, draw bars with `fill`, and report what cannot be fixed by layout.

Use `image_gen` for complete demo images during the design/review phase. During sprite production, assemble and polish the final mockups using actual sprites; do not replace the assembly with a painted screen. Generate only the sprites in the user's requested production scope; report each `MISSING_ELEMENT` otherwise. Give every production screen its background as Backgrounds and art describes.

## 5. Check

For each scene background, run the profile checks in [Background separation and multisize](references/backgrounds.md) and inspect the clean and UI-overlay boards. Geometric PASS does not prove clean reconstruction, scene composition or visibility behind UI. Keep the exported QA current with the image, profile and layout; profile-based exports stop on stale or failed geometry checks.

Before showing a result, complete the [full-composite visual review](references/mockup.md#scene-composition-and-asset-fit): exposed body cuts, unintended floating props and mismatched scene/UI relationships are quality faults even when every individual asset is attractive and scripts pass. Repair them within the existing generation limits before delivery, or report the unresolved fault rather than presenting it as finished.

```bash
py -3 <skill>/scripts/uikit.py qa ui_art/<kit>
```

Run this before showing an assembled sprite mockup result. Demo-only reviews use visual inspection of the complete demo and do not require sprite production or this production QA. View `preview/contact_sheet.png`, `preview/compare.png`, `preview/mockups/` and the images in `preview/nineslice/`. Check the sprite canvases and resolve duplicate directional icons in the new kit before delivery. Fix what the reports and your own eyes find, regenerating a given sheet at most twice. After that, stop and report the problem instead of spending more of the user's quota.

A `needs_review` 9-slice means no stretchable band was found. Regenerate that element with a plainer center, or tell the user it needs manual border work. Never report it as ready. A large-border warning means the corners take most of the sprite, so it only looks right near its original size. Keep it at that size or regenerate it with smaller corners.

## Export

From `$export` or `$mockup` step 8, export only what the shared form selected. Follow [Standalone export and delivery](references/export.md). Apply the same Photoshop rules to standalone UI element and component PSD requests, using their approved references.

- **PSD.** Follow [Photoshop source and export](references/photoshop.md) before building any PSD. For standalone PSD requests too, list local installs with `scripts/photoshop.py` and require a user choice before building; save the selected `photoshop` object in `briefs/export.json`. Use that installation for screen PSDs, component masters, edits and verification. `uikit.py psd` reads this choice and stops if it is missing or invalid; reopen the export form to choose again. Never fall back to generic `Photoshop.Application` or another installed version. Rebuild reusable UI with native shape layers and layer effects, and match the approved demo at least 95%. Keep complex icon, decor, illustration and VFX artwork as clean, full-resolution embedded Smart Objects. Keep ordinary interface copy live where supported; preserve decorated lettering as artwork/Smart Objects and export its composed PNG, following the typography rules. Use [shape recipes](references/recipes.md) for supported native constructions and finish other details in Photoshop.
- **Component master.** Only when `components_psd` was selected, create a separate `export/psd/components.psd` with each component at its optimized sprite size. Verify 9-slice at the sizes in which it will be used. Deliver it with any independently selected screen PSDs in `export/psd/<layout>.psd`.
- **UI kit and demos.** `ui_kit` is one combined selection. `delivery.py build` writes selected sprites/fonts and freshly assembled demo PNGs to `export/delivery/UI/`. Shared resources go under dynamic `Base/<actual family>/` folders; screen-specific resources go under their screen folder, with completed images in `demo/`. Create no empty or fixed category skeleton and export each identical resource only once. The low-level `uikit.py export --png-only` remains a rendering helper, not a separate form choice.
- **Unity.** Only when `unity` was selected, `uikit.py unity` writes `export/unity/<layout>.json` with the hierarchy, inferred anchors, parent-relative positions, sizes, sprites, 9-slice borders, text, font and links. Identify anchors that need adjustment. This is an assembly guide for Unity.
- **ZIP/report.** `zip` adds an archive and user-facing report containing only the selected delivery files and necessary dependencies. It must accompany another output choice. Internal QA reports are working data, not an implicit request for every export format.
- **Delivery.** Check the saved PSDs and actual Photoshop renders. Use `export/psd_report.json` as the script's report, and account for any native Photoshop edits made afterward. List delivered files, verified fidelity and remaining warnings, including missing fonts and failed effects. Report the number of images generated.
