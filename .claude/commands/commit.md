---
name: commit
description: Run checks, commit with AI message, and push
---

1. No lint/typecheck tooling detected in this repo yet (no package.json,
   pyproject.toml, go.mod, or Cargo.toml found). Skip step 1 until a
   project config exists, then re-run `/minimal-claude:setup-commits`.

2. Review changes: `git status` and `git diff`

3. Generate commit message:
   - Conventional Commits format (feat:, fix:, docs:, refactor:)
   - Be specific and concise
   - One line preferred

4. Commit and push:
   ```bash
   git add -A
   git commit -m "your generated message"
   git push
   ```
