# UI kit standard

Use the base set and naming conventions from the **Yêu cầu thành phần** column in the [UI KIT tab](https://docs.google.com/spreadsheets/d/1zZy5cT3bZbI8JQrbhKSgvPdclbgrJoAIcFF5YrATkug/edit?gid=712893616#gid=712893616). Names are lowercase with `_`, inside the family folder shown, such as `buttons/btn_yellow`.

## Base set

| Group | Folder | Minimum | Name |
|---|---|---|---|
| Button | `buttons/` | 6 colors: blue, green, yellow, red, gray, dark. Plus a special button for Play, Fight, Battle or special purchases, in 3 colors: yellow, green or blue, gray | `btn_<color>`, `btn_sp_<color>`, such as `btn_yellow`, `btn_sp_green` |
| Panel / Popup | `popups/` | At least 1 basic popup or panel | `popup_<function>` or `popup_<screen>`, such as `popup_normal`, `popup_noads` |
| Font | `fonts/` | A compact set matched by role to the approved demo, often 1–3 families/weights where appropriate. Do not force a mismatched single font or a hard family limit; follow [typography](fonts.md). | the font's own file name |
| Title frame | `titles/` | 6 colors: blue, green, yellow, red, gray, dark | `title_<color>`, such as `title_yellow` |
| Background | `backgrounds/` | A gradient background, cropped small when possible, and a looping pattern of 256 x 256 px | `bg_<screen>`, `pattern_<theme>`, such as `bg_main`, `pattern_animals` |
| Common icons | `icons/` | The list below | as listed |
| Currency | `currency/` | Coin or cash in at least 5 tiers, gem in at least 5 tiers | `set_coin_<n>`, `set_gem_<n>`, such as `set_coin_1`, `set_gem_3` |
| Common shapes | `shapes/` | Square, circle and equilateral triangle on a 256 px frame: plain; with a 4 px outline; with 8 px and 12 px corners; with those corners and a 4 px outline. All solid white `#ffffff` | `shape_<rectangle\|circle\|poly>[_<corner>px][_outline]`, such as `shape_rectangle_outline`, `shape_poly_12px` |
| Color palette | `style/palette.json` | Primary, secondary, accent, neutral light, neutral dark, text | recorded with `palette`, not a sprite |
| Reward frame | `rewards/` | 160 x 160 px squares, at least normal and special | `reward_normal`, `reward_special` |
| Loading bar | `bars/` | A fill and a background on the same canvas size, fill in at least 3 colors: yellow, white, green or blue | `loading_bar_<color>_a` for the fill, `loading_bar_<color>_b` for the background, such as `loading_bar_yellow_a` |

**Common icons:** `icon_settings`, `icon_sound_on`, `icon_sound_off`, `icon_music_on`, `icon_music_off`, `icon_vibrate_on`, `icon_vibrate_off`, `icon_noti`, `icon_info`, `icon_play`, `icon_pause`, `icon_replay`, `icon_tick`, `icon_lock`, `icon_unlock`, `icon_star`, `icon_watch_ads`, `icon_remove_ads`, `icon_gifts`, `icon_next`, `icon_add`, `icon_back`, `icon_time`, `icon_close`, `icon_edit`, `icon_hand_tutorial`, `icon_rank_1`, `icon_rank_2`, `icon_rank_3`, `icon_cup_bronze`, `icon_cup_silver`, `icon_cup_gold`.

Keep a single upright sprite when icon directions differ only by a horizontal flip, vertical flip or rotation. For example, reuse `icon_next` for Back if both use the same arrow artwork. Keep `icon_back` when Back uses a different design, such as a hooked return arrow. Keep separately drawn on/off, lock/unlock and tier icons where the artwork differs.

Trim generated sprites to the artwork and align both canvas dimensions to multiples of four. Keep the 256 × 256 shape and looping pattern canvases, the 160 × 160 reward frame, and matching canvas sizes for each loading fill and track.

Shapes are plain geometry, so draw them with the script rather than `image_gen`:

```bash
py -3 <skill>/scripts/uikit.py shapes ui_art/<kit>
```

## Names for everything else

Screen-specific parts and art follow the same pattern, `<function>_<description>[_<color>][_<screen>]`, with these prefixes: `btn`, `popup`, `title`, `bg`, `pattern`, `icon`, `set`, `shape`, `reward`, `loading_bar`, `frame`, `tab`, `bar`, `slot`, `badge`, `char`, `item`. Examples: `tab_yellow_shop`, `frame_item_rare`, `badge_sale`, `char_hero_idle`, `item_sword_01`.

## States

The normal button has a bare name such as `btn_yellow`. Use it for press feedback in the game. The `states` command derives `btn_yellow_disabled`. Generate a separate state such as `btn_yellow_locked` when the art differs. Older kits with `_normal` or existing `_pressed` files still work.
