# Standalone export and delivery

`$export` accepts existing UI mockup images or existing kit layouts. It needs no setup, generated wireframe or generated mockup. Read this flow from `$export` and from `$mockup`'s optional export step. Supplied screens are the design targets; generating new concepts or running `$mockup` first is not a prerequisite.

## Start and collect only export information

1. Resolve/create the kit and `.active` as `SKILL.md` describes. Start `state.py <kit> begin export`; record progress so `$info`, command switching, resume and `$reset` work for export-only sessions.
2. Preserve chat attachments and prefill the form with `delivery.py add-source <kit> "<file>" [--screen <screen>]`. Repeat for several files. ZIP input is unpacked into `inputs/`; do not edit originals. The command only drafts the form; it is not submission or approval to use old saved output choices.
3. Open `ask.py export <kit> --out briefs/export.json` every time and keep waiting for SUBMITTED. Existing layouts can be selected directly. Otherwise use supplied image files, each with an optional screen name and note. Ask no genre/gameplay questions. Reuse relevant notes and fonts already supplied.
4. The form permits these five independent multi-select choices:

| Value | Label | Meaning |
|---|---|---|
| `ui_kit` | Bộ UI kit và ảnh demo | One combined choice: shared sprites, screen-specific elements and completed PNG demos reconstructed from those components. |
| `components_psd` | Bộ UI kit (PSD) | An editable `components.psd` master with separate components at their actual sprite sizes. |
| `screen_psd` | PSD từng màn | A PSD for each selected screen/version, with UI groups, live text and artwork separated. |
| `unity` | Dữ liệu ghép Unity (JSON) | Assembly data, inferred anchors and required resource dependencies. Does not construct engine scenes. |
| `zip` | Gói ZIP và báo cáo | An archive of the selected files and dependencies, resource mapping, checks and remaining limits. Requires at least one other choice. |

Do not automatically enable every format, force Unity JSON, or split demos back into a separate selection. An internal render or QA file is working data, not another requested deliverable. The two PSD choices show the local Photoshop version picker. Require an explicit choice even for a single install, use that executable throughout creation and verification, and never fall back to the registered default or another version. The form also asks how to treat the PSD background.

## Prepare supplied mockups without setup

View each supplied source. If its screen name is blank, infer it from its content and tell the user; update `sources[].screen` in the export brief before preparation. Shared names identify versions of the same screen. Use different names for different screens. Preserve the source image's English UI copy or translate retained interface copy to English as `SKILL.md` requires.

```bash
py -3 <skill>/scripts/delivery.py prepare ui_art/<kit>
```

This reads actual image dimensions, records each source's path, hash, size/orientation and allocated layout stem in `briefs/export_sources.json`, and updates the export brief's selected layouts. It creates no `setup.json`. Different screens may have different dimensions. `NEEDS_RECONSTRUCTION` means proceed with the work below, not stop or require another command. Preparation is resumable; unchanged sources retain their allocated layout names.

The helper can fall back to a filename-based name, but visual identification should happen first. If an image exceeds the layout limit, agree a uniform working resolution and retain the original; do not silently stretch it. PSD sources need a readable composite preview or must be opened in Photoshop; never infer design details from filenames alone.

## Reconstruct the requested assets and layouts

Follow [sprite fidelity, clean edges and material alpha](sprite-quality.md) for faithful native-size restoration, preserved antialiased contours, zero extra feather, smooth material color and solid-core alpha. Match shadow/FX darkness or brightness, softness and spread to the demo. Process effects separately internally, then deliver one composed PNG per asset by default. An authorized repair of a delivered kit reuses its existing submitted choices; open the export form only for a new export command or changed/missing selections. Limit sample repairs to the requested assets, and wait for user review before a wider replacement when requested.

For supplied demos, identify shared surfaces, controls, icons, art, backgrounds, font and screen-specific parts across all selected screens. Record sources and the reconstruction plan in `briefs/export_reconstruction.md`. Reuse existing source assets where available. Keep genuine visual/state variants; deduplicate the same artwork across screens. A source screenshot is a reference, not an extracted UI kit or an editable PSD.

- Use [Photoshop source and export](photoshop.md) for native reusable shape/effect construction, clean full-resolution Smart Objects and live text. Apply those rules when building assets from a flattened demo. Reconstruct obscured UI parts and preserve clean alpha edges; report inferences and limits when the source cannot determine hidden details.
- Follow [Background separation and multisize](backgrounds.md) on every scene that needs it. Determine targets from export notes or each image's actual base size, with default test ratios in that image's orientation. Setup is not needed. Preserve a complete cleaned/expanded background master and separate foreground subjects when one plate cannot satisfy the requested range.
- For PNG components and complex artwork, use the built-in `image_gen` tool when isolation/reconstruction/outpainting is needed; read `imagegen` first and view local edit targets. Announce the intended image-edit count within the requested reconstruction scope. Respect any agreed limits, reuse existing work and approvals, and ask only when exceeding that scope/count. No new concept-review loop is required for an already supplied design target.
- Process generated sheets with `uikit.py slice`, or import clean isolated files with `uikit.py import --map`. Never hand-edit the manifest. Preserve source names for assets from an existing kit. Follow [reference-based typography](fonts.md): visually match fonts by role, keep actual files/weights and report substitutions honestly; a screenshot alone does not identify or recover a font file. Export intentional decorated English lettering as named PNG resources with their FX, not generic live-text replacements.
- Build `mockups/<allocated_layout>.json` using each source's own dimensions, with the source as `reference`, real element references, ordinary text where appropriate and imported lettering artwork where required. Measure text-only boxes from the usable faces, excluding shadow padding, icons and decorative peaks. Reassemble the screen from those resources; do not treat the complete demo screenshot as a background containing baked UI. Do not invent extra screen features from the generic screen minimum when the request is to reproduce a supplied demo.
- Render and compare at the source size, run relevant sprite/9-slice QA, and inspect both components and reassembled demos. Use the background profile's clean and per-layout overlay checks. Existing kit layouts enter at this validation/reuse step rather than regenerating art unnecessarily.

## Organize the combined UI kit and demos

The output is a structure pattern, not a fixed category list:

```text
UI/
  Base/
    <actual shared asset family>/...
  <screen name>/
    demo/<screen>__v1.png
    <unique screen assets and optional meaningful groups>
```

`Base` holds components that are shared or intended for repeated use across screens. Its family folders are chosen from the actual game's assets: use suitable names for surfaces, controls, backgrounds, typography, icons, effects or other families that really exist. Create only populated folders. Never pre-create a fixed Button/Popup/BG/Font skeleton from an example kit. Screen folders use the actual screen names and each has `demo/` for the selected fully assembled PNG versions. Put an asset only in one location: promote common resources to Base, reuse that file from other screens and do not copy it into every screen folder. Preserve real differences instead of merging similar but distinct designs.

`delivery.py build` detects shared use across distinct screen names and deduplicates identical RGBA pixels/dimensions even when source files have different names or PNG metadata. It retains alias/resource mappings. For semantic classification that cannot be inferred from file paths alone, write optional `briefs/export_folders.json`:

```json
{
  "screens": {"home": "Main", "shop": "Shop"},
  "families": {"buttons": "Controls", "currency": "Currency"},
  "assets": {"icons/gem": "Currency"},
  "screen_groups": {"shop": {"currency": "coin_set"}},
  "base": ["buttons/*"]
}
```

These are optional names for this particular game, not defaults every game must use. `base` can promote a reusable component even if it currently appears in only one selected screen. Families are otherwise taken from actual element families. Screen-only assets are placed under that screen; add meaningful subgroups only when needed. Do not use Base as a screen name. Do not create empty folders. Native font files retain their format; scene backgrounds retain the full image rather than becoming 9-sliced transparent sprites.

## Build only the selected formats

- **`ui_kit`:** the delivery helper copies the deduplicated assets/fonts and freshly renders every selected version into its screen's `demo/`. It does not substitute the supplied screenshot for a reassembled demo. Resource mappings and 9-slice data are recorded in the internal delivery report.
- **`screen_psd`:** run `uikit.py psd <kit> --layout <layout> --background <choice> --art image` for each selected layout, using the saved Photoshop choice. Finish/verify in the same Photoshop and update `export/psd_report.json` after native edits. The proof must retain the chosen `photoshop`, current `layout_sha256`, `psd_sha256`, fidelity evidence and warnings. Pending JSX is not a verified PSD.
- **`components_psd`:** build `export/psd/components.psd` in the selected Photoshop, with reusable components as native editable shapes/effects, separate live labels and full-resolution art in embedded Smart Objects. Use a targeted JSX and `photoshop.run_photoshop(script, timeout, selected)` when automation is needed; do not create unrelated screen PSDs just to produce the master. Reopen it, inspect native layers and actual-size transparent artboard exports, verify 9-slice, render and compare against the approved source. Write `export/components_report.json` with `verified: true`, the chosen `photoshop`, current `psd_sha256`, the `resources` map described below, actual fidelity evidence and unresolved warnings. Set verified only after those checks, not after mere file creation.
- **`unity`:** run `uikit.py unity <kit> --layout <layout>` per selected layout. It records the current layout hash. Delivery remaps sprite/background references to the single copied resource location. If `ui_kit` was also selected, reuse its UI tree; otherwise include only the necessary resource dependencies under `Unity/Assets`, without generating unselected demo/PSD outputs. Call out inferred anchors or missing font bindings that still need engine adjustment.
- **`zip`:** package the selected files and required dependencies plus the user-facing report, never all historical exports, input uploads or hidden working data.

The component proof's `resources` is `{element_id: pixel_hash}` for every selected image alias, where the hash is `delivery.pixel_hash` over its actual RGBA dimensions and pixels. Obtain the selected set using `delivery.collect(kit, brief['layouts'])`; this prevents an old master that omits current resources from being delivered. After manual Photoshop edits update the PSD hash and record what was checked; never invent a verification score.

```bash
py -3 <skill>/scripts/delivery.py build ui_art/<kit>
```

Use `--force` only when replacing the existing generated delivery was requested. The script builds the selected files in a staging directory before replacing `export/delivery/`. Missing layouts, stale/failed background checks, missing PSD verification or stale Unity data stop packaging. The delivery manifest is saved to `export/delivery_report.json`; `$info` reads it even without setup. Internal renders, scripts and QA reports stay in their working folders.

Inspect the final selected files and assembled demo PNGs, report actual paths, screenshot fidelity, inference/missing-font/9-slice limits and total generated image count in Vietnamese. Never claim the art is verified from file existence or geometry alone. Mark export done only after delivering the requested outputs; do not ask the user to run another prerequisite command to continue.
