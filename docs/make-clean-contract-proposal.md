# Brand palettes and the Make_Clean theme contract

Notes for a later decision on the Make_Clean_PPTX side. Nothing here is needed for Make_Colors to work: the brand palettes it builds pass contract v1 as it is.

## What contract v1 already allows

The contract fixes the **lightness order** of `accent1` to `accent6` (dark to light on a light theme, at least 1.1:1 between neighbours) and the text colour on each fill. It does not fix the hue. So a brand with three or four colours fits without any change: each colour takes the step nearest its lightness, the steps in between are shades of the nearest brand colour, and every pair still passes. Greyscale and colour-blind views keep six distinct steps because the steps differ in lightness first.

## Proposals (all opt-in, defaults unchanged)

| # | Proposal | Why | Cost |
|---|---|---|---|
| 1 | Tag visuals that read the accents as a **scale** (heat grids, levels, layers, maturity steps) as `sequential` in the index, and let deck.json ask for `"accent_scale": "tints"`: those visuals then use tints of `accent1` (`lumMod`/`lumOff`) instead of `accent2`–`accent6`. | With a multi-colour brand ramp, a five-level scale shows five brand colours: it stays ordered by lightness, but reads more like categories than levels. Charts and categorical visuals should keep the brand colours. | Index column + generator switch; contract unchanged |
| 2 | Let a brand pick the **emphasis** slot separately from the dark panels, e.g. `"emphasis": "accent3"` for key numbers and highlight words. | `accent1` is both the strongest emphasis and the dark panel colour. A brand whose main colour is mid-tone (orange, yellow, cyan) cannot carry white text, so its main colour lands on `accent3` or `accent4` and is not the emphasis colour. | Token remap at build; one new contract pair (emphasis on paper, 3:1 for large text) |
| 3 | A `"logo_dark"` key for dark covers and dark slides. | Dark themes and the dark divider need a light logo; today one logo is used everywhere. Make_Colors can produce a light version of a one-colour logo. | One key, placement rule unchanged |
| 4 | Keep the 1.1:1 minimum step. | Make_Colors already checks it in greyscale and three colour-blind simulations, which is stricter in practice; raising it would leave less room for exact brand colours. | None |
| 5 | Sort `pairs` in theme-contract.json by text and fill instead of usage. | The order changes whenever a visual is added, which makes copies of the contract look different when only the counts changed. | Generator only |

## Interoperability with Make_Style_PPTX

Make_Colors brands a deck in one of two ways, so the order of the skills does not matter:

- at build time, through Make_Clean's `"theme"` key;
- afterwards, with `apply_theme.py`, which replaces only the theme's colour and font schemes and the master's colour map. Slides, shapes and shape names (Make_Style's role tags `<role>#<n> > <field>`) are copied byte for byte.

A Make_Style pack that keeps theme colours and theme fonts (no fixed RGB) is therefore branded exactly like a Make_Clean deck. `apply_theme.py` reports `fixed_colours` so a pack that hard-codes colours shows up at once.
