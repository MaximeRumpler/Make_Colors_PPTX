---
type: llm
weight: 3
---

The agent ran `scripts/extract_candidates.py` on `site.css`, proposed roles from its candidates (green #0F6E5A as the main colour, the amber as a second colour) instead of assuming the first colour found is the primary one, then built and checked the theme. Fail if it skipped extraction or built the theme without proposing the roles.
