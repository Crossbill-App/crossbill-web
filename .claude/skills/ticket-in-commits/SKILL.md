---
name: ticket-in-commits
description: Use when a ticket is large enough to want breaking into commits, or has a reference/spike implementation to port — plans the work as bite-sized commits with the user, then drives each one through an implementation subagent, a report-only review subagent, revdiff, and a commit.
---

# Working a ticket as bite-sized commits

One ticket, one PR, several commits a reviewer can read in order. Each commit
ends green: `ruff check`, `pyright`, `lint-imports`, `ruff format --check`,
the test suite, and jscpd under its threshold (CLAUDE.md has the commands).

## 1. Plan with the user before touching code

Read the ticket, its epic, and the reference implementation if one exists.
Then propose the commit breakdown and stop. The user approves it before any
code is written.

A good breakdown:

- **Each commit ends with working, tested behaviour.** Prefer vocabulary →
  smallest end-to-end path → one capability per commit, over "all the types",
  "all the guards", "all the tests".
- **A defence and the code it guards land together.** Splitting them ships a
  commit with a knowingly open hole. When a defence turns out to be inherent
  to a function's job (path traversal in an href builder, media-type guessing
  in a manifest reader), pull it forward into that commit and say so.
- **Name the decisions that are the user's**, with a recommendation and the
  trade-off. Naming, degrade-vs-refuse, drop-vs-publish. Use AskUserQuestion
  when the answer changes the code's shape.

Re-scope the tail openly as commits land — earlier ones absorb work and later
ones shrink or dissolve.

## 2. The loop, per commit

**Implement** — dispatch a subagent with a spec precise enough that it never
guesses: files to create, behaviour rule by rule, the tests to write, what is
out of scope and which commit owns it, the verification commands, and an
instruction to report disagreement plainly rather than comply against its
judgement. It leaves the work uncommitted.

**Review** — dispatch a second subagent, report-only, on the finished work.
Rank simplification above correctness: the first question is what buys
nothing. List the deliberate decisions so it does not re-litigate them, and
require it to demonstrate any claimed bug by running it. Ask for a ranked
verdict: ready as is, ready with N edits, or rework.

**Verify the headline finding yourself.** Run it before acting on it. This
also catches the case where the reviewer is right that *you* were wrong.

**Fix** — a separate pass, yours or a third subagent's, then mutation-check
every behaviour: break it in the smallest way that should fail a test,
confirm one does, revert. A survivor means the test is decoration.

**revdiff** — see below.

**Commit** — the message carries the reasoning: what the code does, why the
shape was chosen, what a departure from the reference buys.

## 3. revdiff is the user's gate

Write a description file first — what the commit is, the departures worth
their eye, the numbers that back a claim — then:

```bash
R=$(ls -d "$HOME"/.claude/plugins/cache/revdiff/revdiff/*/.claude-plugin/skills/revdiff | tail -1)
"$("$R/scripts/resolve-launcher.sh" launch-revdiff.sh \
   "$HOME/.claude/plugins/data/revdiff-revdiff")" \
  --untracked --description-file=<path>
```

`--untracked` matters: new files are invisible without it. Exit 10 means
annotations came back on stdout; empty output means the user reviewed and
approved. It blocks for as long as the review takes, so set the bash timeout
to its maximum — and if the tool times out, the launcher is still running,
so wait for the user rather than relaunching.

Answer a question annotation by checking, not from memory: to justify a
pragma, delete it and re-run the type checker.

## 4. Carry these into every implementation prompt

- **The comment and docstring rule**, quoted, with a file already in the
  branch named as the calibration. Without it the agent adopts the
  reference's house style, and the commit gets reworked. The rule: public
  symbol one line, a body only for a constraint the code cannot express and
  then two lines at most; private helpers usually none; a comment earns its
  place by stating a reason the code cannot express; test names state the
  behaviour, so a docstring repeating the name is noise.
- **The reference is a guide, not a source.** Say which departures are
  deliberate and why. A spike carries bugs — this workflow found five in one:
  a container-escape hole, an uncatchable `zlib.error`, an lxml comment that
  discarded a whole table of contents, a legal attribute token list missed by
  an exact-match selector, and a `refines`-scoped property read as global.
- **A real corpus, where one exists.** `~/Code/crossbill/xpoint-cfi/test-books`
  holds 13 real EPUBs. "976 TOC entries, unchanged" is worth more than any
  hand-built fixture for proving a refactor changed nothing.
- **Cost claims get measured**, with the measured figure in the assertion
  message. A memory-guard test that only asserts an exception passes whether
  or not the guard runs where it is supposed to.
