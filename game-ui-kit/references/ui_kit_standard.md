# UI kit standard

The base set a new kit must have, and the names to use. It is the user's house standard, so it overrides generic naming. Names are lowercase with `_`, inside the family folder shown, such as `buttons/btn_yellow`.

## Base set

| Group | Folder | Minimum | Name |
|---|---|---|---|
| Button | `buttons/` | 6 colors: blue, green, yellow, red, gray, dark. Plus a special button for Play, Fight, Battle or special purchases, in 3 colors: yellow, green or blue, gray | `btn_<color>`, `btn_sp_<color>`, such as `btn_yellow`, `btn_sp_green` |
| Panel / Popup | `popups/` | At least 1 basic popup or panel | `popup_<function>` or `popup_<screen>`, such as `popup_normal`, `popup_noads` |
| Font | `fonts/` | At most 3 fonts, or 3 weights of one font (thin, regular, bold). Best: one medium-weight font across the whole game | the font's own file name |
| Title frame | `titles/` | 6 colors: blue, green, yellow, red, gray, dark | `title_<color>`, such as `title_yellow` |
| Background | `backgrounds/` | A gradient background, cropped small when possible, and a looping pattern of 256 x 256 px | `bg_<screen>`, `pattern_<theme>`, such as `bg_main`, `pattern_animals` |
| Common icons | `icons/` | The list below | as listed |
| Currency | `currency/` | Coin or cash in at least 5 tiers, gem in at least 5 tiers | `set_coin_<n>`, `set_gem_<n>`, such as `set_coin_1`, `set_gem_3` |
| Common shapes | `shapes/` | Square, circle and equilateral triangle on a 256 px frame: plain; with a 4 px outline; with 8 px and 12 px corners; with those corners and a 4 px outline. All solid white `#ffffff` | `shape_<rectangle\|circle\|poly>[_<corner>px][_outline]`, such as `shape_rectangle_outline`, `shape_poly_12px` |
| Color palette | `style/palette.json` | Primary, secondary, accent, neutral light, neutral dark, text | recorded with `palette`, not a sprite |
| Reward frame | `rewards/` | 160 x 160 px squares, at least normal and special | `reward_normal`, `reward_special` |
| Loading bar | `bars/` | A fill and a background on the same canvas size, fill in at least 3 colors: yellow, white, green or blue | `loading_bar_<color>_a` for the fill, `loading_bar_<color>_b` for the background, such as `loading_bar_yellow_a` |

**Common icons:** `icon_settings`, `icon_sound_on`, `icon_sound_off`, `icon_music_on`, `icon_music_off`, `icon_vibrate_on`, `icon_vibrate_off`, `icon_noti`, `icon_info`, `icon_play`, `icon_pause`, `icon_replay`, `icon_tick`, `icon_lock`, `icon_unlock`, `icon_star`, `icon_watch_ads`, `icon_remove_ads`, `icon_gifts`, `icon_next`, `icon_add`, `icon_back`, `icon_time`, `icon_close`, `icon_edit`, `icon_hand_tutorial`, `icon_rank_1`, `icon_rank_2`, `icon_rank_3`, `icon_cup_bronze`, `icon_cup_silver`, `icon_cup_gold`.

Shapes are plain geometry, so draw them with the script rather than `image_gen`:

```bash
py -3 <skill>/scripts/uikit.py shapes ui_art/<kit>
```

## Names for everything else

Screen-specific parts and art follow the same pattern, `<function>_<description>[_<color>][_<screen>]`, with these prefixes: `btn`, `popup`, `title`, `bg`, `pattern`, `icon`, `set`, `shape`, `reward`, `loading_bar`, `frame`, `tab`, `bar`, `slot`, `badge`, `char`, `item`. Examples: `tab_yellow_shop`, `frame_item_rare`, `badge_sale`, `char_hero_idle`, `item_sword_01`.

## States

The normal state has no suffix: `btn_yellow`. The `states` command derives `btn_yellow_pressed` and `btn_yellow_disabled` from it. A state that needs a different drawing, such as `btn_yellow_locked`, is generated and named the same way. Older kits that end their base names in `_normal` still work.
