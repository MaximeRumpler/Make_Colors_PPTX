---
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Skill, Bash, Read, Write, Edit, Glob, Grep]
tags: [nominal, french]
---

Crée d'abord un fichier `site.css` dans le dossier courant avec exactement ce contenu : `:root { --brand-primary: #0F6E5A; --brand-accent: #F0A01E; } body { color: #222; font-family: "Demo Grotesk", Inter, sans-serif; } a { color: var(--brand-primary); }`. C'est le CSS de mon site (marque inventée). Fais-moi un thème PowerPoint aux couleurs de ma marque à partir de ce fichier.
