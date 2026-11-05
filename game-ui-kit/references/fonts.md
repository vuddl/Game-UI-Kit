# Choosing a font

Order of preference:

1. A font file the user or the kit provides. Search the kit's folders for `.ttf` and `.otf`, copy the file into `ui_art/<kit>/fonts/`, and check its license if the user plans to ship it.
2. A font named by the user. Add it from the catalog below, or ask for the file.
3. Otherwise, choose one from the catalog that suits the art, and tell the user which and why.

Use one font for the whole kit, or two at most: a display font for titles and numbers, and a plain one for long text. The first file in `fonts/` by name is the default, and a layout's `font` key overrides it. Name files so the default sorts first if there are two.

```bash
py -3 <skill>/scripts/uikit.py fonts ui_art/<kit> --add "Lilita One"
```

This downloads the font with its license from the Google Fonts repository, and needs network access. Run `fonts ui_art/<kit>` with no `--add` to check that each layout's text has glyphs in the font.

| Art style | Fonts in the catalog |
|---|---|
| Casual, cartoon, voxel, kids | Lilita One, Titan One, Luckiest Guy, Changa One |
| Bold arcade, mobile action | Bungee, Passion One, Russo One |
| Pixel art, retro | Press Start 2P, Silkscreen, VT323 |
| Sci-fi | Audiowide, Russo One |
| Military, shooter | Black Ops One, Russo One |
| Fantasy, medieval | MedievalSharp, Cinzel Decorative |
| Horror | Creepster |

Check the result in a mockup. Display fonts lose legibility below roughly 3 percent of the screen's short side, and all-caps fonts such as Luckiest Guy and Bungee ignore lowercase.
