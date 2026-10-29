# Roles file and outputs

`build_theme.py` reads a small JSON file that you write once the user has agreed on the roles. Only `primary` is required; everything else has a default that adds nothing.

```json
{
  "name": "Demo Harbour",
  "primary": "#1D4E89",
  "secondary": "#E07A1F",
  "others": ["#2A9D8F", "#F2C14E"],
  "fonts": {"major": "Georgia", "minor": "Arial"},
  "variants": ["light", "dark"]
}
```

| Key | Meaning | Default |
|---|---|---|
| `name` | Theme name shown in PowerPoint; also the file name (`demo-harbour.potx`) | `"Brand"` |
| `primary` | The brand's main colour. Chooses its ramp slot first, and gives its hue to `accent1` unless another brand colour is already that dark | required |
| `secondary` | Second brand colour: on the ramp, and the hyperlink colour (darkened if too faint) | none (links use `accent2`) |
| `others` | Third and fourth brand colours, most important first. Greys are skipped (put them in `neutrals`) | none |
| `ramp` | `"brand"`: every brand colour on the slot nearest its lightness. `"single"`: six shades of the primary only, the others set aside. `"drift"`: the hue slides from the primary (accent1) to the secondary (accent6), for close hues | `"brand"` (same as `"single"` with one colour) |
| `fonts.major`, `fonts.minor` | Heading and body fonts; one given = used for both | Arial |
| `neutrals` | Light variant: `text` (dk1), `background` (lt1), `body` (dk2), `surface` (lt2) | `111111`, `FFFFFF`, `404040`, `F2F2F2` |
| `dark` | Dark variant: same four keys | `F5F5F5`, `121212`, `D9D9D9`, `262626` |
| `tint_neutrals` | `true`: neutrals take a touch of the primary hue, same lightness | `false` |
| `accents`, `dark_accents` | Six colours used as they are, when the brand guide already defines a ramp. Checked, not corrected | generated |
| `variants` | `["light"]`, `["dark"]` or both | both |

## How the slots are filled

| Slot | Light variant | Dark variant |
|---|---|---|
| `dk1` | text colour (`ink`) | dark background (the master maps `bg1` to it) |
| `lt1` | background (`paper`) | light text colour |
| `dk2` | body text (`ink2`) | cards (`surface`) |
| `lt2` | cards (`surface`) | body text |
| `accent1`–`accent6` | brand colours and their shades, darkest to lightest | the same, lightest to darkest |
| `hlink` | secondary, else `accent2` | secondary, else `accent2` |
| `folHlink` | `accent3` | `accent3` |

Each brand colour takes the slot nearest its own lightness (brute force over the arrangements: a slot where the exact colour passes wins, the primary weighs most, `accent1`/`accent3`/`accent5` win near-ties because charts use them first); a slot without a brand colour takes a shade of the nearest one. An arrangement that merges two neighbours in a colour-blind view is skipped for the next best. `brand_slots` in the report says, for each colour, the slot where it stayed exact, or `null` when a shade replaced it.

The lightness of each accent is solved from the contract: every text and fill pair that the Make_Clean layouts use reaches its minimum (4.5:1 or 3:1) with a small margin, and neighbouring accents stay 1.1:1 apart. If the user's own neutrals make a pair impossible (a mid-grey text colour, a tinted background), the files are still written and the report lists what fails.

## Outputs

- `<name>.potx`: light template carrying the theme. Opens in PowerPoint as a template; *Design → Browse for Themes* applies it to any deck.
- `<name>-dark.potx`: dark template (colour map swapped on the master).
- `<name>.thmx` with `--thmx`: theme only, light variant (a `.thmx` has no master, so no dark variant).

The JSON report gives the files, the twelve slot values per variant, where each brand colour went (`brand_slots`, `notes`), the contract findings, colour-blind and greyscale warnings (`view_warnings`), font notes, and a `deck_json` snippet.

## Applying it in Make_Clean_PPTX

In deck.json, next to `"slides"` (relative paths are read from the folder of deck.json):

```json
"theme": "brand/demo-harbour.potx",
"logo": "brand/logo.png",
"logo_alt": "Demo Harbour"
```

Add `"theme_fonts_fallback": "Arial"` when the brand font is not a common font. Make_Clean replaces the colours and fonts of the deck in one pass, applies the dark colour map if the source has one, and prints contract findings as warnings. Then run its `lint_deck.py --contrast` and `render_check.py`, or this skill's `preview_deck.py`, which does both and shows before and after.

## Applying it to a deck that already exists

```bash
python3 scripts/apply_theme.py build/deck.pptx --theme brand/demo-harbour.potx [--out ...] [--fonts-fallback Arial]
```

Same result as the `"theme"` key, without rebuilding: the colour and font schemes of every slide master's theme are replaced, and the dark colour map is applied from a `-dark.potx`. Every other part (slides, shapes, shape names, pictures, notes) is copied byte for byte, so it works on:

- a Make_Clean deck built earlier;
- the same deck restyled by Make_Style_PPTX: its shapes use theme colours and fonts too, and its role tags (shape names `<role>#<n> > <field>`) are kept, so branding before or after restyling gives the same deck;
- any other deck: the report counts its fixed colours (`fixed_colours`), which a theme cannot change.

The input is never overwritten (default output: `<deck>-<theme>.pptx`). `preview_deck.py --pptx deck.pptx --theme ...` shows the same deck before and after, with Make_Clean's lint and render.
