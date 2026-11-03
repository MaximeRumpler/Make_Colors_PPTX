---
type: llm
weight: 3
---

The agent used the make-colors-pptx skill: it wrote a roles file, ran `scripts/build_theme.py` and `scripts/check_theme.py`, and produced a light and a dark `.potx`. The roles were proposed to the user (or taken from the user's own words) with the blue as the main colour. Fail if the agent edited theme XML by hand, skipped the contract check, or shipped a variant with findings without saying so.
