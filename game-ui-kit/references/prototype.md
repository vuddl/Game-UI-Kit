# Prototype, project continuity and Figma delivery

Use this branch when a game already runs or a project provides a real screen inventory. Keep the existing Setup, wireframe, full, mockup, revise and Export forms. Do not replace them with a separate dashboard. The six user commands remain unchanged; helpers below are internal operations.

## Resolve the project before Setup

Read applicable project instructions. Before creating a new kit or asking the user to run Setup, look for `ui_art/.active`, existing setup/briefs and `.gui/handoff.json`. A kit may live outside the engine repo. Run:

```text
py -3 <skill>/scripts/workflow.py resolve <project-path>
```

The project registry maps a project path to its actual kit and is populated when Setup is submitted. Reuse that kit across chats. Missing state in a new working directory is not proof the project has no setup. If several plausible existing kits remain, ask which to use; do not silently start again. Do not store project-specific paths or Figma IDs in the global skill.

## Setup and the three destinations

The existing Setup form now asks input mode (idea / wireframe / playable prototype). Prefill observed size, genre and gameplay plus choices already made in chat; preserve user edits. For prototype mode collect:

- `project_path`: the actual playable project; inspect how to run it rather than guessing an engine.
- `figma_url`: **one Figma file for the whole project**, with editable access. It receives captured screenshots, gameplay/flows, session-approved demos and final exported demos in distinct sections. Never ask for a second file URL merely to move to another phase.
- `approved_demo_folder`: **Folder lưu demo chốt trong phiên**. When the user approves a demo, archive that exact selected PNG here and sync its existing screen entry on Figma.
- `exported_demo_folder`: **Folder chứa demo chốt được xuất khi xuất file**. It contains the final demo images produced at Export. It is both the export-image destination and the source for the separate final-demo section. Include descendants; do not confuse it with session approvals.
- `layout_workflow`: improve layout during mockup, or review flow/wireframes first. A request to go directly to mockup selects the former; do not ask again or impose a wireframe gate.

Require missing prototype destinations clearly, explain each field and reuse them later. Folder paths are local directory paths, not web URLs. The two folders must differ. Setup grants the configured save/sync operations when the corresponding images are approved/exported, not arbitrary changes elsewhere. When continuing a legacy project, inspect its saved settings and established mappings, and prefill missing fields before asking only for unresolved information. Standalone Export remains usable without Setup or Figma.

## Survey and capture

Discover available engine MCP, playable builds or computer-use tools. Use the relevant skill for the actual engine/tool. No hard dependency on Unity MCP is assumed. Play the requested scope and inspect source to find states that are easy to miss. Do not claim play/capture from source reading alone. A whole-game survey begins at startup/Loading; a selected slice only covers its declared scope.

Save original PNGs under `captures/<screen>/<case>.png`, grouped by screen. Record cases, steps, prerequisites, images and whether they were reached by play or a runtime trigger. Source-only, blocked and unchecked cases remain explicit; do not invent images or claim complete coverage from file counts. Do not silently change game logic, persistent user progress or missing features just to obtain a screenshot. Prefer a separate available test profile; explain a concrete blocker when project changes would be required.

Maintain `briefs/project_screens.json` (merge discoveries, don't discard existing cases):

```json
{
  "scope": "Selected playable flow",
  "screens": [
    {
      "screen": "lobby", "label": "Lobby", "group": "Startup",
      "function": "Enter modes and manage player equipment",
      "cases": [
        {"case": "default", "status": "captured", "method": "played",
         "steps": ["Launch game", "Dismiss first popup"], "path": "captures/lobby/default.png"}
      ],
      "layout_decision": "during_mockup"
    }
  ],
  "current_transitions": [],
  "proposed_transitions": []
}
```

This is a schema example, not observed game content. Cases use `captured`, `source-only`, `blocked` or `not-checked`; add a reason when not captured. Keep the catalog's `current_transitions` as evidence and proposals separately. An existing project's own screen list can be normalized with `workflow.py catalog <kit> --file <inventory.json>`; retain its names, groups and distinct screen IDs. The form combines project inventory, briefs and approved demos; real entries replace generic suggestions. Keep checkbox selection, descriptions, per-screen attachments and manual additions. Show each screen as chưa làm / đang sửa / đã chốt. Discover the list before opening a screen-selection form.

## Present the existing game on Figma

Use the configured file, inspect existing sections/mappings and read the relevant Figma skill before required tool calls. Reuse an existing project page if suitable. Put a concise genre/gameplay/core-loop/progression description at the top, based on observed facts; label inferences. Group original screenshots by actual mode/flow with editable captions and transition arrows labeled by action/condition. Keep detailed state lookup and add navigation when scale warrants it. Preserve screenshot pixels/copy/aspect ratio. Not every project has AS92's modes or seven groups.

Use separate sections for **UI hiện tại**, optional **Luồng/bố cục đề xuất**, **Demo chốt trong phiên**, and **Demo bản cuối sau Export**. References to section/page/image/card node IDs belong in `briefs/project_sync.json`, not in this skill. For a new file section inspect the file first and match its organization; never overwrite another project's section.

## Layout and mockup

Prototype screenshots determine required functions, data and states, not a locked composition or art style. Design anew using the approved screens' palette, materials, lettering, icon language and reusable masters. Improve grouping, hierarchy and placement while retaining functionality. Discuss gameplay/unlock-rule changes or added/removed features separately.

- **Before mockup:** present only necessary flow/layout changes for review. Store the user's approval and approved wireframe. Stable screens can keep their layout.
- **During mockup:** make the new layout in the demo itself and briefly state meaningful changes. The user reviews layout and appearance together. Do not demand an extra wireframe approval.

An explicitly approved wireframe or demo still locks the scope it approved. A style anchor does not force every new screen to use the first screen's layout. Apply [exact sprite reuse](reuse.md) throughout demo design/revision.

## On demo approval

Only the user's explicit approval of the exact current image counts; selecting a draft to refine is not approval. In the same task, save and sync without asking for destination permission again:

```text
py -3 <skill>/scripts/workflow.py approve <kit> --screen <stable-id> --label "Screen name" --group "Flow" --image "<exact-approved.png>" --evidence "User approval message" [--filename existing-name.png]
```

This copies bytes to an immutable snapshot, canonical image and the configured session folder; it updates the demo register/screen brief, queues reusable-component inspection and marks Figma pending. It does not generate artwork or silently mark a queue item remotely synced. Existing project filenames/mappings win over default filenames. Reconcile an unmanaged/external edit before replacement; the helper preserves the approval and reports a folder error rather than destroying that file. Repeat the same approved image after fixing an unavailable destination; do not require approval again.

Run `workflow.py sync-plan <kit> --namespace approved`, then actually update through the Figma connector. Each existing screen keeps its card/image node; replace its image fill, preserving the exact source ratio. Add new screens once in the right flow. Reconcile file contents when mapping is missing or a previous call's result is uncertain. Inspect the resulting image/layout before:

```text
py -3 <skill>/scripts/workflow.py mark-synced <kit> --namespace approved --key <screen-id> --sha256 <current-hash> --node-id <image-node-id> --url "<verified-node-link>"
```

This only records evidence of the connector operation. Never call it on assumed success. Preserve section/card IDs in each queue record as needed. Keep error/pending status if access, copy or verification fails; retry one transient failure after reading state, then report the concrete incomplete part. Do not keep retrying uncertain writes or duplicate a card. Approval alone enables internal sprite extraction/reuse; it does not order PSD, Unity or other external deliverables.

## Final exported demos and folder imports

`delivery.py build` copies only selected, freshly assembled UI demo PNGs to the second folder, preserving screen/demo/version paths and exact bytes; it records copy failures without undoing successful delivery. The separate `exported` queue follows the full source-relative path (case-insensitive) plus SHA-256. Scan with:

```text
py -3 <skill>/scripts/workflow.py sync-plan <kit> --namespace exported
```

On Export completion or a user request to update that folder, reconcile the queue against Figma, add new images, replace changed ones in their existing image nodes, skip verified unchanged hashes and verify the result. Mark each with `mark-synced --namespace exported --key <relative-path-key> ...`. Do not replace the separate session-approval section. Missing source files never imply permission to delete Figma entries. Ambiguous screen names remain unchanged until clarified. No watcher/schedule is implied; reuse/update an established automation only if the user requested one.

When the user asks to import a folder of session-approved demos, use the first folder and established IDs/filenames. A folder confirmed to contain approved images supplies batch approval evidence; don't ask the user to reapprove every file. A mixed draft folder needs identification of the approved subset. Do not confuse final export images with session approval of new designs.

## Questions, drafts and cross-chat handoff

Before an interactive choice use `workflow.py question <kit> --text "..." --options "Option 1" "Option 2"`. Keep the Question pending until the user actually submits. Do not answer it yourself, close/replace it, open its downstream form or conclude the step prematurely. With an immediate-return async question tool, keep waiting with bounded waits; continue only independent work. If a client requires yielding, preserve the pending question and resume it on the reply rather than substituting a browser form. Skip, dismissing the panel and elapsed time do not choose an option.

After the actual reply record `workflow.py answer <kit> --choice "Option 1" --evidence "Actual reply"`, then open the corresponding existing form. If the user's current message already explicitly selects scope/action, record/use that answer directly and don't ask again. A user explicitly changing/canceling the task can supersede the pending question via `cancel-question --evidence "..."`; silence/Skip cannot.

The form reuses a still-running instance; it does not kill it to open another. Input drafts and uploads persist under `.gui/drafts/`, with local browser recovery. Drafts are not submissions or approvals. Wait for Hoàn thành/SUBMITTED before dependent work. A failed submission keeps the form and draft. If the user explicitly requests replacing/updating a form, use `ask.py ... --replace` after saving its draft; this closes only that form and retains its data. Never use replacement to bypass an unanswered Question. Never claim recovery of unsent Question text that the host did not expose.

`state.py step/done` automatically refresh `.gui/handoff.json`. Before suggesting a new chat, checkpoint and note current screen/draft, pending revision/question/form, exact style/master sources, configuration, approvals and unsynced items. Suggest the handoff after many revision rounds at a convenient saved milestone, not in the middle of an unresolved choice. Don't invent a cache threshold or promise image quality from changing chats. Do not create a chat without an explicit request. A new chat in the same project reads the registry/handoff/briefs and resumes, with no new Setup or repeated configuration.
