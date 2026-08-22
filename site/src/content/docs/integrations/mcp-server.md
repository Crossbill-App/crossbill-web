---
title: MCP server
description: Let Claude and other AI assistants read and work with your Crossbill library through the Model Context Protocol.
---

The Crossbill MCP server exposes your library to AI assistants that speak the
[Model Context Protocol](https://modelcontextprotocol.io/) — Claude Desktop,
Claude Code, and any other MCP client. The assistant gets the same operations
the web UI has: your books, highlights, notes, tags, flashcards, digests and
reflections, through the Crossbill REST API.

It runs on your machine, talks to your own Crossbill server, and logs in as you
with your own account. Nothing is shared with anyone your assistant is not
already talking to.

## What you can do with it

Once the server is connected, you ask in plain language and the assistant picks
the tools. Some things it is good at:

- **Work through a book's highlights.** "Find every highlight in *Thinking, Fast
  and Slow* about base rates and tag them `statistics`."
- **Collaborate on notes** "Read chapter 4 and draft a note, linked to the
  chapter and to the three highlights it builds on."
- **Answer from your library rather than from the model.** With
  [semantic search](../../features/semantic-search/) on, "what have I read about
  deliberate practice?" searches your own highlights, notes and digests.
- **Turn reading into cards.** Ask for [flashcard](../../features/flashcards/)
  suggestions from a chapter, a highlight or a note, then create the ones worth
  keeping.
- **Analyze your reading patterns over time.** Check which topics in the book interested you over time if you kept returning into it in different life situations.

## Installing

The server lives in the `mcp-server` directory of the
[crossbill-web repository](https://github.com/Crossbill-App/crossbill-web). It
is a Python package that needs Python 3.11 or newer:

```bash
cd mcp-server
# pip
pip install -e .
# uv
uv tool install --editable .
```

That installs a `crossbill-mcp` command, which is what your MCP client will
run.

## Configuring

The server takes three environment variables, and refuses to start without all
three:

| Variable             | What it is                    | Example                 |
| -------------------- | ----------------------------- | ----------------------- |
| `CROSSBILL_URL`      | Base URL of the Crossbill API | `http://localhost:8000` |
| `CROSSBILL_EMAIL`    | The email you registered with | `user@example.com`      |
| `CROSSBILL_PASSWORD` | That account's password       |                         |

It logs in with those credentials, then keeps the session alive by refreshing
its token, so you configure it once.

### Claude Desktop

Add the server to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "crossbill": {
      "command": "crossbill-mcp",
      "env": {
        "CROSSBILL_URL": "http://localhost:8000",
        "CROSSBILL_EMAIL": "your-email",
        "CROSSBILL_PASSWORD": "your-password"
      }
    }
  }
}
```

### Claude Code

The same block works in Claude Code's MCP settings, or add it in one command:

```bash
claude mcp add crossbill \
  -e CROSSBILL_URL=http://localhost:8000 \
  -e CROSSBILL_EMAIL=user@example.com \
  -e CROSSBILL_PASSWORD='password' \
  -- crossbill-mcp
```

### Running it directly

Useful for checking that it starts and can log in:

```bash
export CROSSBILL_URL=http://localhost:8000
export CROSSBILL_EMAIL=your-email
export CROSSBILL_PASSWORD=your-password
crossbill-mcp
```

It speaks MCP over stdio, so on its own it will just sit there waiting for a
client.

## Deleting data

Seven tools delete things. Five of them — `delete_note`, `delete_flashcard`,
`delete_tag`, `delete_tag_group` and `delete_bookmark` — throw away something
you can write again. Two of them throw away more:

- **`delete_book`** removes a book with all its chapters and highlights. Syncing
  the book from KOReader again recreates it, but the notes, flashcards, tags and
  digests Crossbill kept alongside it are gone.
- **`delete_highlights`** removes highlights from a book along with their
  flashcards and bookmarks. Syncing the book again does not bring them back;
  marking one of the passages again on the e-reader restores the highlight
  itself, but the flashcards and bookmarks stay gone.

Neither of those two runs on the assistant's say-so. Before calling the API, the
server asks *you* to confirm through MCP elicitation, spelling out what is about
to go — the book's title with its chapter and highlight counts, or how many
highlights and from which book. Only an explicit yes goes through; declining or
dismissing the prompt leaves everything in place.

The prompt comes from the server rather than from the assistant, so it cannot be
talked around. If your MCP client does not support elicitation, the deletion is
refused outright and you are pointed at the Crossbill web UI instead — a client
that cannot ask you is a client that cannot delete.

All seven deletion tools are annotated `destructiveHint: true` (so is
`cancel_job_batch`), and every read-only tool is annotated `readOnlyHint: true`,
so clients can treat the groups differently. If you allowlist the whole Crossbill server in Claude Code,
keep the deletions behind a prompt:

```json
{
  "permissions": {
    "ask": ["mcp__crossbill__delete_*"]
  }
}
```

## Tools that need a provider

Some tools depend on what your Crossbill server has configured, and say so
rather than failing obscurely:

- **AI provider** (`AI_PROVIDER`): chapter digest generation, reading-session
  summaries and the three flashcard-suggestion tools. Without one, they answer
  that AI features are not enabled.
- **Embedding provider** (`EMBEDDING_PROVIDER`): `semantic_search` and
  `find_related`. Without one, they answer that semantic search is not enabled.

See [Optional components](../../getting-started/optional-components/) for
turning either on.

## Tool reference

The server registers 50 tools. Full descriptions and arguments are in
[`mcp-server/README.md`](https://github.com/Crossbill-App/crossbill-web/blob/main/mcp-server/README.md).

### Books

`list_books`, `get_book`, `get_recently_viewed_books`, `set_reading_stage`,
`delete_book`

### Highlights

`get_highlights`, `update_highlight_note`, `tag_highlight`, `untag_highlight`,
`delete_highlights`

### Highlight labels

`get_book_highlight_labels`, `get_global_highlight_labels`,
`update_highlight_label`, `create_global_highlight_label`

### Notes

`create_note`, `get_note`, `get_book_notes`, `update_note`, `delete_note`

`update_note` replaces a note in full — anything you omit is cleared, so read
the note with `get_note` first and resend what you want to keep.

### Tags

`get_book_tags`, `create_tag`, `update_tag`, `delete_tag`,
`create_or_rename_tag_group`, `delete_tag_group`

### Flashcards

`get_flashcards`, `create_flashcard`, `update_flashcard`, `delete_flashcard`,
`suggest_flashcards_for_chapter`, `suggest_flashcards_for_highlight`,
`suggest_flashcards_for_note`

The three suggestion tools only propose question-and-answer pairs; nothing is
saved until one is passed to `create_flashcard`.

### Chapter digests and background jobs

`get_chapter_digest`, `generate_chapter_digest`, `answer_digest_question`,
`get_book_digests`, `generate_book_digests`, `get_digest_generation_status`,
`get_job_batch`, `cancel_job_batch`

`generate_chapter_digest` makes one AI call and can take tens of seconds.
`generate_book_digests` instead enqueues the whole book as a job batch for the
[background worker](../../getting-started/optional-components/), which you then
poll.

### Bookmarks

`list_bookmarks`, `create_bookmark`, `delete_bookmark`

### Reading

`get_reading_sessions`, `get_chapter_content`, `get_reading_session_summary`

### Semantic search

`semantic_search`, `find_related`

### Reflection

`get_book_reflection`, `update_book_reflection`

Like `update_note`, `update_book_reflection` replaces the reflection in full.
