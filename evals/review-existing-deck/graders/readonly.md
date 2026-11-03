---
type: llm
weight: 3
---

The agent ran `scripts/check_theme.py` on deck.pptx and Make_Clean's `lint_deck.py --contrast` when available, reported the result in plain words, and left deck.pptx byte for byte unchanged (any fix is offered as a copy made with `apply_theme.py`). Fail if deck.pptx was overwritten or edited.
