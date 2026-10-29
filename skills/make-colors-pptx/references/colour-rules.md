# Colour rules

The rules behind the theme this skill builds, with the reason for each. Use them when you propose roles to the user and when you explain why a brand colour moved.

## 1. One strong colour, many quiet ones (60-30-10)

A slide reads best when about **60 %** of it is the background (paper, white or near-white, or near-black on a dark theme), about **30 %** is quiet structure (text, cards, rules, light fills), and about **10 %** is the brand colour, used for emphasis: the key figure, the main series, a dark panel.

*Why:* emphasis only works by contrast with what is not emphasised. When everything is in the brand colour, nothing stands out and the eye has no entry point. Make_Clean's layouts are already built this way. Map the brand onto them; do not add colour.

In the theme: the brand's signature hue goes on `accent1` (strongest) or `accent2` (when it is mid-tone). The other accents are lighter or darker steps of the same hue. `lt1`/`lt2` (background, cards) and `dk1`/`dk2` (text) stay neutral or barely tinted.

## 2. The accents are a ramp, not a palette

`accent1` to `accent6` go from strong to faint (light theme: dark to light; dark theme: light to dark), each step at least **1.1:1** brighter or darker than the previous one. This is the theme contract of Make_Clean_PPTX.

*Why:* charts, heat grids, levels and layers read the accents in order, and the text colour on each fill is fixed: paper text on `accent1` and `accent2`, ink text on `accent3` to `accent6`. Six unrelated brand hues turn charts into a rainbow with no order, and put white text on yellow or black text on navy.

A brand with several colours: pick **one** as the ramp hue (the one people recognise the brand by). A second hue can be used for links (`hlink`) or, with `"ramp_drift": true`, as a slow drift of the ramp from the primary to the secondary hue, when the two are close (blue to teal, red to orange). Say so to the user: the other brand colours stay available for pictures and the logo, not for the layouts.

## 3. Contrast: 4.5:1 for text, 3:1 for large text and graphics

Thresholds are WCAG 2.x (SC 1.4.3 and 1.4.11):

| What | Minimum |
|---|---|
| Normal text (below 18 pt, or below 14 pt bold) | 4.5:1 |
| Large text (18 pt and above, or 14 pt bold and above) | 3:1 |
| Lines, markers, chart bars that carry meaning on their own | 3:1 |

*Why:* below these ratios, text becomes hard to read for people with low vision, on a projector in a lit room, or on a phone in daylight, which is most audiences at some point. The Make_Clean libraries use 10 pt text on nearly every pair, so 4.5:1 applies almost everywhere.

Tight spots to check first: captions (`muted`, which is the text colour lightened) on cards, light accents as text on `accent1` (dark slides), and `accent5` on `accent2`. Captions are why `dk1` must be very dark: with the default `#F2F2F2` cards, any text colour lighter than `#111111` puts captions on cards under 4.5:1 (on white alone, the limit is about `#212121`). A lighter brand text colour needs lighter cards.

Brand colours that are mid-tone (most oranges, yellows, light greens, cyans) cannot carry white text and cannot be read as text on white. They become a light step of the ramp or are darkened; `build_theme.py` says which and why.

## 4. Never rely on colour alone

About 1 man in 12 and 1 woman in 200 see colours differently (mostly red and green). Greyscale printing and poor projectors do the same to everyone.

*Why the ramp helps:* a ramp differs in **lightness**, which survives every colour-vision deficiency and greyscale. `check_theme.py --preview` shows the theme in greyscale and with protanopia, deuteranopia and tritanopia; neighbouring accents must stay at least 1.1:1 apart in every view. Red versus green as the only difference between two series always fails this.

Charts in Make_Clean take the accents in the order `accent1, accent3, accent5, accent2, accent4, accent6`, so that neighbouring series are far apart on the ramp.

## 5. Dark themes

The background is dark and the text light. In PowerPoint terms, `dk1` keeps the dark colour and the slide master's colour map swaps background and text (`bg1 = dk1`, `tx1 = lt1`). `accent1` is the **lightest** accent, because it carries the background colour as text; the ramp then darkens towards `accent6`.

*Why:* Make_Clean reads text on `accent1` as "paper", so on a dark theme `accent1` panels become light panels with dark text. This is expected: the dark slides of a light deck become the light slides of a dark deck.

Avoid pure black (`#000000`) backgrounds with pure white text: the glare tires the eyes. Near-black and off-white (`#121212` and `#F5F5F5`, the defaults) read better.

## 6. Fonts

The theme has two fonts: headings (major) and body (minor). Make_Clean's character limits are measured with Arial.

- Prefer fonts that ship with Windows, macOS and Office (Arial, Calibri, Georgia, Segoe UI, Aptos and the like). A web font that is not installed is replaced by PowerPoint on the machine that opens the deck, with different widths.
- When the brand font is a web font, suggest a close common font (`extract_candidates.py` lists one), or keep the brand font and set `theme_fonts_fallback` in deck.json.
- A wider font fills boxes sooner: always look at the before/after preview and the lint after a font change.

## 7. The logo

The logo is not part of the theme. Make_Clean places it from the `"logo"` key of deck.json, on the covers and the closing slide. Its contrast is not checked: on a dark theme, or on the dark cover, give a light version of the logo.

## Ten quick checks before delivery

1. One brand hue on the ramp, the others named and set aside with the user's agreement.
2. `accent1` or `accent2` is the brand colour, or the nearest readable shade (and the user knows).
3. `check_theme.py` passes for every variant delivered.
4. The greyscale view still shows six distinct steps.
5. Text colour is near-black, `#111111` or darker (light theme) or off-white (dark theme), never mid-grey.
6. Background is white or near-white, near-black on dark, never a saturated colour.
7. Fonts are common, or a fallback is set.
8. The before/after preview shows no overflow and nothing unreadable.
9. A light logo exists for dark covers, if a dark variant is delivered.
10. The user saw the before/after image and agreed.
