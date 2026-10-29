<div align="center">

[![Make_Colors_PPTX](docs/banner.svg)](https://github.com/MaximeRumpler/Make_Colors_PPTX)

*From your content, first Make_Clean, then add your colours.*

[![License](https://img.shields.io/badge/License-EUPL--1.2-10B981?style=flat-square&labelColor=1C2333)](LICENSE)
[![Status](https://img.shields.io/badge/Status-preview-10B981?style=flat-square&labelColor=1C2333)](#status)
[![Companion](https://img.shields.io/badge/Companion_of-Make__Clean__PPTX-10B981?style=flat-square&labelColor=1C2333)](https://github.com/MaximeRumpler/Make_Clean_PPTX)

</div>

* * *

## What it does

Make Colors PPTX is a companion *skill* of [**Make_Clean_PPTX**](https://github.com/MaximeRumpler/Make_Clean_PPTX).

Make_Clean_PPTX gives your notes their **form**: one message per slide, a matching design and chart, in black, grey and white. Make Colors PPTX gives them **your brand**: it reads what you have, builds a PowerPoint theme from it, and applies it to the clean deck.

You give it whatever you have:

| **A brand guide** | **A website** | **Example files** | **A logo** |
|:---:|:---:|:---:|:---:|
| your brand guidelines, as a PDF | its colours and fonts, from a saved page or its CSS | a deck, template or theme in your colours | its main colours, from the image |

It lists the colours and fonts it finds, and the assistant agrees with you on which one leads. Then it builds a real PowerPoint theme, light and dark, checks that text stays readable and that charts stay clear (also in greyscale and for colour-blind readers), and shows you the deck before and after. It never changes your content or layout.

* * *

## How it works

| **Find** | **Choose** | **Build** | **Check** | **Show** |
|:---|:---|:---|:---|:---|
| Colours and fonts found in your files, offline | You and the assistant pick the main colour and fonts | A `.potx` theme, light and dark, that PowerPoint and Make_Clean_PPTX both use | Contrast 4.5:1 for text, 3:1 for large text and charts; greyscale and colour-blind views | The same deck, before and after, in one image |

**Why one main colour.** Make_Clean's slides read their six accent colours as steps, from strong to faint: the main series, the dark panels, the light fills. So your main colour becomes a family of shades, and a colour that cannot carry readable text (most yellows and oranges) moves to the nearest readable shade. The skill says so, and why. The rules, with their reasons, are in [colour-rules.md](skills/make-colors-pptx/references/colour-rules.md).

In Make_Clean's deck.json, two lines apply your brand:

```json
"theme": "brand/your-brand.potx",
"logo": "brand/logo.png"
```

The theme also works on its own in PowerPoint: *Design → Themes → Browse for Themes*.

* * *

## Status

Preview, not released yet. The skill folder is [skills/make-colors-pptx](skills/make-colors-pptx): copy it next to `make-clean-pptx` in your assistant's skills folder. It needs Python 3.9 or later with python-pptx, Pillow and lxml; the before/after images also need LibreOffice. The first release will be announced on [Make_Clean_PPTX](https://github.com/MaximeRumpler/Make_Clean_PPTX).

Just ask, in your own words:

```text
Put this deck in our colours: here is our logo and our website.
Make a PowerPoint theme from our brand guidelines.
Mets ce deck aux couleurs de notre marque, voici notre logo.
```

* * *

## The Make PPTX set

Part of [**Make PPTX**](https://github.com/MaximeRumpler/Make_PPTX), a set of three skills from your notes to a finished deck.

| **Make_Clean_PPTX** | **Make_Style_PPTX** | **Make_Colors_PPTX** |
|:---|:---|:---|
| **Form.** Notes in, clean deck out. | **Look.** The same deck in another style. | **Brand.** Your colours, fonts and logo. |
| [Install](https://github.com/MaximeRumpler/Make_Clean_PPTX#install) · [Gallery](https://maximerumpler.github.io/Make_Clean_PPTX/) | In preparation | In preparation |

Each one works on its own; together they take you from raw notes to a finished, branded deck. All of them work in Claude Code, Claude.ai, Codex and other assistants that read skills.

* * *

## License

[EUPL-1.2](LICENSE), the open source licence of the European Union: free to use; if you share an improved version, share it under the same licence. **The presentations and themes you make are yours**, with no obligation ([NOTICE](NOTICE)).

<div align="center">

Built by [**Maxime Rumpler**](https://github.com/MaximeRumpler) · [![KairosTech](https://img.shields.io/badge/Kairos-Tech-10B981?style=flat-square&labelColor=1C2333&logoColor=white)](https://github.com/KairosTech-fr) · [kairostech.fr](https://kairostech.fr)

<sub>With thanks to the creators and contributors of [impeccable](https://github.com/pbakaus/impeccable), whose design skills for AI agents inspired this set, and of Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), which guides how its texts are written.</sub>

</div>
