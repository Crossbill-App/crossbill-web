---
title: Semantic search
description: Search your highlights, notes and chapter digests by meaning, across all books and languages.
---

Semantic search finds content by **meaning**. A search for *attention* finds a
highlight about staying focused even if the highlight does not contain the word.
A search in one language also finds content in other languages.

Semantic search is optional. The search fields appear only after you set an
embedding provider. See [Turning it on](#turning-it-on).

## Searching all books

The search field in the app bar searches your whole library. Type a query and
press Enter. The search runs only when you press Enter, because each search
calls the embedding model.

**Books** whose title or author contains your query are listed first. These
match by text, so you can find a book by typing part of its title.

Below the books is one list of results, best match first. It contains:

- **Highlights**, with their book and chapter.
- **Notes**, with their title and the start of the body.
- **Chapters**, matched by their [chapter digest](../chapter-digests/).

Click a result to open it. You can also use the arrow keys to move through the
list, Enter to open a result, and Escape to close the list. On a narrow screen,
the app bar shows a search icon that opens the search in full screen.

Weak matches are left out, so a search with no good matches shows no results.

## Searching one book

Two tabs on a book page have their own search field:

- **Notes**: filters the notes by meaning. It works together with the kind and
  tag filters, and sorts the notes by best match.
- **Structure**: shows the chapters whose digest matches. Chapters without a
  digest do not show up.

## Indexing your library

Crossbill indexes new content in the background. Uploading highlights, writing
or editing a [note](../notes/), and generating a
[chapter digest](../chapter-digests/) each start an indexing job. The
[background worker](../../getting-started/optional-components/#background-worker)
runs these jobs.

Content that existed before you turned on semantic search needs to be indexed
once. Go to **Settings → Background processes** and choose **Run text embedding
for the library**. The page shows the progress, and you can cancel the run. The
run skips content that is already indexed, so you can run it again after you
add more books.

## Turning it on

Semantic search is off until you set `EMBEDDING_PROVIDER`. These settings are
separate from the `AI_*` settings, so chapter digests and semantic search can
use different providers.

Local, with Ollama:

```
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=bge-m3
EMBEDDING_BASE_URL=http://localhost:11434/v1
```

Hosted, with OpenRouter, using your existing `OPENROUTER_API_KEY`:

```
EMBEDDING_PROVIDER=openrouter
EMBEDDING_MODEL_NAME=baai/bge-m3
```

`EMBEDDING_BASE_URL` is required for `ollama`. For `openrouter` it is optional
and defaults to `https://openrouter.ai/api/v1`.

Semantic search also needs PostgreSQL with the `vector` extension, version 0.8
or newer. The `docker-compose.yml` uses the `pgvector/pgvector:pg18` image,
which includes it.

Crossbill stores vectors with 1024 dimensions, which is what `bge-m3` produces.
Switching to a model with a different size requires a database migration and
indexing the whole library again. Choose the model before you index your
library.
