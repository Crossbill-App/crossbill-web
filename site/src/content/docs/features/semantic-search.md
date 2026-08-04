---
title: Semantic search
description: Optional meaning-based search over notes, highlights and chapter digests, across books and languages.
---

Semantic search finds content by meaning rather than by exact words. It embeds
your **notes**, **highlights** and **chapter digests** into a vector index, so
related material surfaces even when it uses different wording — and even when it
sits in a different book or a different language from the one you searched in.

This is what ordinary text search cannot do for you: a search for _"how habits
form"_ can turn up a highlight that never uses the word "habit".

## It is optional

Semantic search is **off unless an embedding provider is configured**. Without
one, Crossbill still gives you the plain text search on highlights and books,
and nothing else changes.

## What it needs

- **PostgreSQL with pgvector, version 0.8 or newer.** The bundled
  `pgvector/pgvector:pg18` image ships 0.8.6.
- **An embedding provider**, set through `EMBEDDING_PROVIDER`,
  `EMBEDDING_MODEL_NAME` and — for Ollama — `EMBEDDING_BASE_URL`. Ollama and
  OpenRouter are supported.

The exact environment variables are in
[Optional components](../../getting-started/optional-components/).

## Indexing what you already have

New and edited content is embedded by background jobs as you go, so the index
keeps up with itself. Content that existed before you turned semantic search on
is indexed by a one-off backfill:

```
POST /api/v1/semantic/backfill
```

The backfill also prunes index entries whose source has been deleted. Progress
shows up through the usual job-batch views, so you can watch a large library
work through.
