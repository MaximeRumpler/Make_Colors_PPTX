<div align="center">

[![Make_Colors_PPTX, an agent skill that puts your brand on a PowerPoint deck: three or four brand colours, fonts and logo, from brand guidelines, a website or example files](docs/banner.svg)](https://github.com/MaximeRumpler/Make_Colors_PPTX)

*Give your deck your brand. Three or four colours, your fonts and your logo, from what you already have.*

<sub lang="fr">En français : mettez votre présentation aux couleurs de votre marque, à partir de ce que vous avez déjà.</sub>

[![CI](https://img.shields.io/github/actions/workflow/status/MaximeRumpler/Make_Colors_PPTX/ci.yml?branch=main&style=flat-square&label=CI&color=10B981&labelColor=1C2333)](https://github.com/MaximeRumpler/Make_Colors_PPTX/actions/workflows/ci.yml)
[![Licence](https://img.shields.io/badge/Licence-EUPL--1.2-10B981?style=flat-square&labelColor=1C2333)](LICENSE)
[![Status](https://img.shields.io/badge/Status-preview-10B981?style=flat-square&labelColor=1C2333)](#install)
[![Make PPTX](https://img.shields.io/badge/Set-Make_PPTX-10B981?style=flat-square&labelColor=1C2333)](https://github.com/MaximeRumpler/Make_PPTX)

</div>

* * *

## What it does

Make_Colors_PPTX is a *skill*: a folder of instructions and small tools that an AI assistant such as Claude or Codex uses to put a brand on presentations.

[Make_Clean_PPTX](https://github.com/MaximeRumpler/Make_Clean_PPTX) gives your notes their **form**, in black, grey and white. Make_Colors_PPTX gives them **your brand**: it reads what you have, builds a real PowerPoint theme from it and applies it to the deck. It never changes your content or your layout.

You give it whatever you have:

| **Brand guidelines** | **A website** | **Example files** | **A logo** |
|:---|:---|:---|:---|
| as a PDF | its colours and fonts, from a saved page or its CSS | a deck, template or theme in your colours | its main colours, from the image |

It lists the colours and fonts it finds, and agrees with you on your three or four brand colours and which one leads. Then it builds the theme, light and dark, checks that text stays readable and charts stay clear, and shows you the deck before and after.

* * *

## Install

| **Claude Code** | **Codex, Cursor, Copilot, Gemini CLI and others** | **Claude.ai or Claude desktop** |
|:---|:---|:---|
| `/plugin marketplace add MaximeRumpler/Make_PPTX`<br>then `/plugin install make-colors-pptx@make-pptx` | `npx skills add MaximeRumpler/Make_Colors_PPTX`<br>It asks which assistant you use. Needs [Node.js](https://nodejs.org). | A ready-to-upload zip comes with the first release. Until then, use one of the first two columns. |

It needs Python 3.9 or later on your computer; the skill tells you if anything is missing. It works offline. The before and after image needs [Make_Clean_PPTX](https://github.com/MaximeRumpler/Make_Clean_PPTX#install) and LibreOffice.

**Update**: Claude Code, `/plugin marketplace update make-pptx`; other assistants, run the `npx skills add` line again.

## Use

Ask in your own words, and attach what you have:

```text
Put this deck in our colours: here is our logo and our website.
Make a PowerPoint theme from our brand guidelines.
Mets ce deck aux couleurs de notre marque, voici notre logo.
```

A deck that is already made, restyled or not, gets the theme without being rebuilt: the skill writes a branded copy and leaves your file as it is. The theme also works on its own in PowerPoint: *Design → Themes → Browse for Themes*.

* * *

## How it works

| **Find** | **Choose** | **Build** | **Check** | **Show** |
|:---|:---|:---|:---|:---|
| Colours and fonts found in your files, offline | You and the assistant pick the three or four brand colours, the leading one first, and the fonts | A `.potx` theme, light and dark, that PowerPoint and Make_Clean_PPTX both use | Contrast 4.5:1 for text, 3:1 for large text and charts; greyscale and colour-blind views | The same deck, before and after, in one image |

**How your colours fit.** Make_Clean_PPTX's slides read their six accent colours as steps, from dark to light: the dark panels, the main series, the light fills. Each brand colour takes the step nearest its own lightness (a navy near the dark end, a yellow near the light end) and the steps in between are shades of the nearest one. A colour that cannot carry readable text there moves to the nearest readable shade of itself; the skill says so, and why. Greys stay for text and cards. The rules, with their reasons, are in [colour-rules.md](skills/make-colors-pptx/references/colour-rules.md).

In Make_Clean_PPTX's deck.json, two lines apply your brand when the deck is built:

```json
"theme": "brand/your-brand.potx",
"logo": "brand/logo.png"
```

* * *

## The Make PPTX set

Part of [**Make PPTX**](https://github.com/MaximeRumpler/Make_PPTX), three skills that take your notes to a finished deck. Each one works on its own.

| **Make_Clean_PPTX** | **Make_Style_PPTX** | **Make_Colors_PPTX** |
|:---|:---|:---|
| **Form.** Notes in, a clean deck out: one message per slide, tested layouts and charts. | **Look.** The same deck in another style: other shapes, arrangements and backgrounds. | **Brand.** Your colours, fonts and logo, from your brand guidelines, website or example files. |
| [Install](https://github.com/MaximeRumpler/Make_Clean_PPTX#install) · [Gallery](https://maximerumpler.github.io/Make_Clean_PPTX/) | Preview · [Install](https://github.com/MaximeRumpler/Make_Style_PPTX#install) | Preview · [Install](https://github.com/MaximeRumpler/Make_Colors_PPTX#install) |

*Start with Make_Clean_PPTX for the structure. Add a style and your brand colours when you need them.*

* * *

## Licence

[EUPL-1.2](LICENSE), the open source licence of the European Union: free to use; if you share an improved version, share it under the same licence. **You own the decks and themes you make, and your brand stays yours.** The EUPL does not apply to them and no attribution is required ([NOTICE](NOTICE)).

<div align="center">

Built by [**Maxime Rumpler**](https://github.com/MaximeRumpler) · [![KairosTech](https://img.shields.io/badge/Kairos-Tech-10B981?style=flat-square&labelColor=1C2333&logoColor=white)](https://github.com/KairosTech-fr) · [kairostech.fr](https://kairostech.fr)

<sub>With thanks to the creators and contributors of [impeccable](https://github.com/pbakaus/impeccable), whose design skills for AI agents inspired this set, and of Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), which guides how its texts are written.</sub>

<p align="right">
  <img src="https://komarev.com/ghpvc/?username=MaximeRumpler&repo=Make_Colors_PPTX&color=44cc11&style=flat-square&label=views" alt="Repository Views" />
</p>

</div>

[[Make_Clean_PPTX]]
