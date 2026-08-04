---
name: start-github-ticket
description: Use when the user provides a GitHub issue/ticket URL (e.g. github.com/Crossbill-App/crossbill-web/issues/NNN) and asks to start working on it — fetches the ticket, moves it to In Progress on the project board, creates a branch, and begins implementation.
---

# Start GitHub Ticket

## 1. Fetch the ticket

```bash
gh issue view <number> --repo Crossbill-App/crossbill-web --json number,title,body,labels,projectItems,url
```

The body is the spec — read it carefully.

## 2. Move it to "In Progress" on the project board

The issue's `projectItems` contains the project item id(s). Find the Status
field and option ids, then set the status:

```bash
gh project list --owner Crossbill-App
gh project field-list <project-number> --owner Crossbill-App --format json
gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> \
  --field-id <STATUS_FIELD_ID> --single-select-option-id <IN_PROGRESS_OPTION_ID>
```

If the issue isn't on the board yet, add it first with `gh project item-add`.
If these commands fail (auth, TLS, permissions), report the failure and ask
whether to continue without the status update — don't silently skip it.

## 3. Create a branch

Work directly in the main repo directory on a new branch: `git checkout -b
<slug>`, a short kebab-case slug from the issue title, optionally prefixed
with the issue number.

Use a worktree only when the user explicitly asks, or when parallel agents
would collide in the same checkout. Then keep it under `.worktrees/<slug>`
(`git worktree add .worktrees/<slug> -b <branch>`) and copy the git-ignored
`.env` into it — the backend/frontend won't start without it. If `.env`
doesn't exist in the main checkout, tell the user and stop; don't fabricate
one.

## 4. Implement

Re-read the acceptance criteria before writing code and follow the usual
project workflow (see CLAUDE.md). Reference the issue number in commits and
the eventual PR so GitHub auto-links them (`Fixes #NNN`).
