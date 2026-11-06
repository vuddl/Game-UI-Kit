# Visual questions

`visual` starts with these questions, before any art is made for a kit. Send them as one message, in the user's language, with every option numbered so the user can answer in one line, such as `1: D:\wf\home.png | 2b1: D:\ref\a.png, D:\ref\b.png - like a but warmer | 3b2`. Then wait. Never guess the answers. Skip a question only when the user's message already answers it.

Files can be one or more paths, or images attached in the chat. Load each with `view_image` before using it.

## The questions

1. **Wireframe:** attach the wireframe files, one per screen.
   - When this kit already has a confirmed wireframe from `wireframe create`, say so and offer it as the default, so the user only answers to replace it.
2. **UI kit**
   a. **Yes:** attach the UI kit folder or files, plus an optional description.
   b. **No:**
      1. **With references:** attach reference images, as many as wanted, plus an optional description. For each, the user may note whether it is for layout or art style; when not noted, treat it as art style.
      2. **No references, create from a description.** Then ask, in the same message:
         - **Colors:** bright, pastel, dark theme, or describe them
         - **UI style:** list the art styles in [catalog.md](catalog.md), numbered, plus "Other: describe it"
         - **Description:** anything else, optional
3. **Background**
   a. **Yes:** attach the background files.
   b. **No:**
      1. Pick from the UI kit's own backgrounds and patterns
      2. Generate new backgrounds in the art style
   - **Description:** optional.

   Offer 3b1 only when question 2 is a, since it needs a kit.

## Saving the answers

Add them to `ui_art/<kit>/brief.json` under `visual`, keeping everything already there:

```json
{
  "visual": {
    "wireframes": {"home": "style/wireframes/home.png"},
    "kit": {"path": "D:/kits/forest_ui", "notes": "use the wood buttons for main actions"},
    "references": [{"file": "style/references/ref_1.png", "role": "style"}],
    "art_style": {"colors": "bright", "style": "Soft Casual", "notes": ""},
    "background": {"source": "generate", "files": [], "notes": "forest, morning light"}
  }
}
```

`kit`, `references` and `art_style` are mutually exclusive by question 2: keep only the one that applies. `background.source` is `files`, `kit` or `generate`.

## What each answer starts

| Answer | Next |
|---|---|
| 1, files given | Copy them to `style/wireframes/`, and set each as its screen layout's `reference`, measured in `keep` mode. Ask which screen a file is when its name does not say. |
| 2a | Role A. Run Existing kit on the folder, then Extend. |
| 2b1 | Role B, from references. Copy them to `style/references/` with their roles. |
| 2b2 | Role B, from a description. Use the chosen style's description from [catalog.md](catalog.md) and the colors in the style guide and every prompt. |
| 3a | Import the files as `backgrounds/bg_<screen>` and use them as the screens' `background`. Ask which screen each is for when unclear. |
| 3b1 | Pick the best kit background or pattern per screen, and say which. |
| 3b2 | Generate backgrounds as Backgrounds and art describes, with the image count first. |
