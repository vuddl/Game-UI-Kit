# Wireframe questions

`wireframe create` starts with these questions, unless the user already answered them in the same message. Send them as one message, in the user's language, with every option numbered so the user can answer in one line, such as `1b | 2: 1, 6, Other: Gacha | 3: 13 | 4: ... | 5: ... | 6: ... | 7a`. Then wait. Never guess the answers.

Ask questions 3 and 4 only for the first wireframe of a new game, that is, when `brief.json` has no `game_type` yet. Later wireframes for the same game reuse them and say so in one line.

## The questions

1. **Orientation**
   a. Portrait, 1080 x 1920
   b. Landscape, 1920 x 1080
   c. Custom size: type width x height
2. **Screens**, pick one or more: list the screens in [catalog.md](catalog.md) by group, numbered, plus "Other: type the name".
3. **Game type**, new game only: list the game types in [catalog.md](catalog.md), numbered, plus "Other: type it".
4. **Gameplay**, new game only: describe the gameplay briefly.
5. **What each screen does:** describe its function. One line per screen when several are picked.
6. **Content by area**, per screen, following the orientation:
   - Portrait: Top, Middle, Bottom
   - Landscape: Top, Left, Right, Bottom

   An area left empty is yours to decide.
7. **Clickable prototype demo** after the wireframe is approved?
   a. Yes
   b. No

## Saving the answers

Write them to `ui_art/<kit>/brief.json`, keeping earlier answers for the same game:

```json
{
  "game_type": "Survival",
  "gameplay": "Move to dodge hordes, weapons fire on their own, pick a skill on each level up.",
  "size": [1080, 1920],
  "orientation": "portrait",
  "prototype": false,
  "screens": {
    "home": {"function": "Start a run, see upgrades and events", "areas": {"top": "level, coin, gem", "middle": "hero and stage", "bottom": "play button, nav bar"}}
  }
}
```

Use the size as every layout's `size`, the areas as the layout's regions and `group` names, and the game type's description from [catalog.md](catalog.md) when choosing the tone and the layout.
