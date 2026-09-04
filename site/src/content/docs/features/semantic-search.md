---
title: Semantic search
description: Searching your highlights, notes and chapter digests by meaning — across every book, and across languages.
---

Semantic search finds content by **meaning** rather than by the words you typed.
Searching for *attention* surfaces a highlight about staying focused even though
it never uses the word, and a query in one language matches content written in
another.

It is optional: the search fields do not appear at all until an embedding
provider is configured. See [Turning it on](#turning-it-on).

## Searching every book

The search field in the app bar searches your whole library. Type a query and
press Enter — the search runs when you submit it, not on every keystroke,
because each query is a call to the embedding model.

**Books** whose title or author contains what you typed are listed first.
Those are matched on the name, not on meaning, so typing a title you half
remember finds the book itself rather than only the passages inside it.

Below them the results are one ranked list, best match first, mixing three kinds
of content:

- **Highlights**, with the book and chapter they came from.
- **Notes**, with their title and the start of the body.
- **Chapters**, matched through their [chapter digest](../chapter-digests/).

Pick a row to open the book, highlight, note or chapter it came from. The arrow
keys move through the list, Enter opens the row you are on, and Escape closes it.
On a narrow screen the app bar shows a search icon instead, which opens the same
search full-screen.

Matches that are only weakly similar are dropped, so a query with nothing to
match comes back empty rather than showing ten confident-looking non-answers.

## Searching inside one book

Two of a book's tabs have a search field of their own, scoped to that book:

- The **Notes** tab filters the notes by meaning. It combines with the kind and
  tag filters — a note has to pass all of them — and orders the survivors best
  match first.
- The **Structure** tab searches the chapter digests and keeps the chapters
  whose digest matched, so a chapter is findable this way once it has a digest.

## Indexing your library

Content is embedded in the background as you produce it: uploading highlights,
writing or editing a [note](../notes/), and generating a
[chapter digest](../chapter-digests/) each queue an embedding job. This is work
for the optional
[background worker](../../getting-started/optional-components/).

Anything that existed before you switched semantic search on needs a one-time
pass. In **Settings → Background processes**, choose **Run text embedding for
the library**. Progress is shown while it runs and you can cancel it partway.
Only content that has not been embedded yet is processed, so running it again
later — after importing a few more books, say — is cheap.

## Turning it on

Semantic search is off unless `EMBEDDING_PROVIDER` is set. The settings are
independent of the `AI_*` ones, so chapter digests and embeddings can use
different providers.

Local, through Ollama:

```
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=bge-m3
EMBEDDING_BASE_URL=http://localhost:11434/v1
```

Hosted, through OpenRouter, reusing `OPENROUTER_API_KEY`:

```
EMBEDDING_PROVIDER=openrouter
EMBEDDING_MODEL_NAME=baai/bge-m3
```

`EMBEDDING_BASE_URL` is required for `ollama` and optional for `openrouter`,
where it defaults to `https://openrouter.ai/api/v1`.

Two more things the feature needs:

- **PostgreSQL with the `vector` extension, version 0.8 or newer.** The
  `docker-compose.yml` uses the `pgvector/pgvector:pg18` image, which has it.
- **The background worker**, which is what writes the embeddings.

The stored vectors are 1024 numbers wide, which is what `bge-m3` produces.
A model of a different width is a database migration and a full re-index rather
than a change of setting, so pick the model before you index the library.
