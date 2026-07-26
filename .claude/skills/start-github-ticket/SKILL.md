---
name: start-github-ticket
description: Use when the user provides a GitHub issue/ticket URL (e.g. github.com/Crossbill-Highlights/crossbill-web/issues/NNN) and asks to start working on it — fetches the ticket, moves it to In Progress on the project board, creates a branch, and begins implementation.
---

# Start GitHub Ticket

Use this when the user drops a GitHub ticket URL and says "start working on this", "implement this", "pick this up", or similar.

## Steps

### 1. Fetch the ticket

Parse owner/repo/number from the URL and read the issue:

```bash
gh issue view <number> --repo Crossbill-Highlights/crossbill-web --json number,title,body,labels,projectItems,url
```

Read the full body carefully — that's the spec for what you're implementing.

### 2. Move ticket to "In Progress" on the project board

The issue's `projectItems` in the JSON output contains the project item id(s). Find the project and set the Status field to "In Progress":

```bash
# List projects to find the right one (usually only one)
gh project list --owner Crossbill-Highlights

# Get the Status field id and "In Progress" option id for the project
gh project field-list <project-number> --owner Crossbill-Highlights --format json

# Set the item status
gh project item-edit \
  --project-id <PROJECT_ID> \
  --id <ITEM_ID> \
  --field-id <STATUS_FIELD_ID> \
  --single-select-option-id <IN_PROGRESS_OPTION_ID>
```

If the issue isn't on the project board yet, add it first with `gh project item-add`.

If any of these commands fail (auth, TLS, missing permissions), report the failure to the user and ask whether to continue without the status update — don't silently skip it.

### 3. Create a branch

**Default: work directly in the main repo directory on a new branch — no worktree.**
Use a short kebab-case slug derived from the issue title, optionally prefixed with the
issue number.

```bash
git checkout -b <branch-name>
```

Check `git branch --list` first if you're unsure the name is free.

#### Worktree (only on request)

Only create a worktree when the user explicitly asks, or when several agents will work
the same repo in parallel and would otherwise collide. Then:

```bash
git worktree add .worktrees/<slug> -b <branch-name>
cp .env .worktrees/<slug>/.env   # git-ignored, not carried across worktrees
```

Keep worktrees under `.worktrees/` so they stay consistent with existing ones. If `.env`
doesn't exist in main, tell the user and stop — don't fabricate one.

### 4. Begin implementation

Start working on the ticket (from the worktree, if you created one). Before writing code:

- Re-read the ticket body and acceptance criteria.
- If the task is non-trivial or ambiguous, invoke `superpowers:brainstorming` before touching code.
- Otherwise apply the usual project workflow (TDD where applicable, pyright/ruff on the backend, eslint/type-check on the frontend — see CLAUDE.md).

Reference the issue number in commits and the eventual PR so GitHub auto-links them (`Fixes #NNN`).

## Quick reference

| Step | Command |
|------|---------|
| Read ticket | `gh issue view <n> --repo Crossbill-Highlights/crossbill-web --json number,title,body,labels,projectItems` |
| Move to In Progress | `gh project item-edit --project-id … --id … --field-id … --single-select-option-id …` |
| Create branch (default) | `git checkout -b <branch>` |
| Worktree (on request only) | `git worktree add .worktrees/<slug> -b <branch>` + `cp .env .worktrees/<slug>/.env` |

## Common mistakes

- **Creating a worktree by default** — work in the main repo directory unless the user asks otherwise or parallel agents need isolation.
- **Skipping the project board update silently** when `gh project` commands fail. Surface the failure instead.
- **Forgetting to copy `.env`** when you *do* use a worktree — it will then fail to start the backend/frontend.
- **Using a branch name that already exists** — check with `git branch --list` first if unsure.
