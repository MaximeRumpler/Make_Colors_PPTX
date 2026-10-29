# Roles file and outputs

`build_theme.py` reads a small JSON file that you write once the user has agreed on the roles. Only `primary` is required; everything else has a default that adds nothing.

```json
{
  "name": "Demo Harbour",
  "primary": "#1D4E89",
  "secondary": "#E07A1F",
  "fonts": {"major": "Georgia", "minor": "Arial"},
  "variants": ["light", "dark"]
}
```

| Key | Meaning | Default |
|---|---|---|
| `name` | Theme name shown in PowerPoint; also the file name (`demo-harbour.potx`) | `"Brand"` |
| `primary` | The brand's signature colour: the hue of the accent ramp. Kept exactly on the nearest ramp slot when the contract allows it | required |
| `secondary` | A second brand colour: used for hyperlinks (darkened if too faint), and for the ramp drift below | none (links use `accent2`) |
| `ramp_drift` | `true`: the ramp hue moves from the primary (accent1) to the secondary (accent6). Only for close hues | `false` |
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
| `accent1`–`accent6` | brand hue, darkest to lightest | brand hue, lightest to darkest |
| `hlink` | secondary, else `accent2` | secondary, else `accent2` |
| `folHlink` | `accent3` | `accent3` |

The lightness of each accent is solved from the contract: every text and fill pair that the Make_Clean layouts use reaches its minimum (4.5:1 or 3:1) with a small margin, and neighbouring accents stay 1.1:1 apart. If the user's own neutrals make a pair impossible (a mid-grey text colour, a tinted background), the files are still written and the report lists what fails.

## Outputs

- `<name>.potx`: light template carrying the theme. Opens in PowerPoint as a template; *Design → Browse for Themes* applies it to any deck.
- `<name>-dark.potx`: dark template (colour map swapped on the master).
- `<name>.thmx` with `--thmx`: theme only, light variant (a `.thmx` has no master, so no dark variant).

The JSON report gives the files, the twelve slot values per variant, where the primary went (or why it could not stay exact), the contract findings, font notes, and a `deck_json` snippet.

## Applying it in Make_Clean_PPTX

In deck.json, next to `"slides"` (relative paths are read from the folder of deck.json):

```json
"theme": "brand/demo-harbour.potx",
"logo": "brand/logo.png",
"logo_alt": "Demo Harbour"
```

Add `"theme_fonts_fallback": "Arial"` when the brand font is not a common font. Make_Clean replaces the colours and fonts of the deck in one pass, applies the dark colour map if the source has one, and prints contract findings as warnings. Then run its `lint_deck.py --contrast` and `render_check.py`, or this skill's `preview_deck.py`, which does both and shows before and after.
