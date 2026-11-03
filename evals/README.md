# Evals

Behaviour checks for the skill, run with Claude Code's plugin eval runner:

```bash
claude plugin eval . --allow-tools "Bash(python3:*)" "Bash(cp:*)" Write Edit --runs 1 --no-publish
```

Each case is a realistic request (`prompt.md`, English or French) and graders that judge the result (`graders/*.md`). They cover what unit tests cannot: does the agent propose the roles and let the user decide, say in plain words when a colour had to change, check the theme, answer in the user's language and leave the user's files alone. Every brand in them is invented. Run them before a release, not on every commit.
