---
title: MCP server
description: Let Claude and other AI assistants read and work with your Crossbill library through the Model Context Protocol.
---

The Crossbill MCP server gives AI assistants access to your library through
the [Model Context Protocol](https://modelcontextprotocol.io/). It works with
Claude Desktop, Claude Code and other MCP clients. The assistant can work with
your books, highlights, notes, tags, flashcards, digests and reflections, the
same as in the web app.

The server runs on your machine and logs in to your Crossbill server with your
account. It sends your data only to the assistant you connect it to.

## What you can do with it

Once the server is connected, ask the assistant in plain language. It chooses
the tools. Some examples:

- **Work through a book's highlights.** "Find every highlight in *Thinking, Fast
  and Slow* about base rates and tag them `statistics`."
- **Write notes together.** "Read chapter 4 and draft a note, linked to the
  chapter and to the three highlights it builds on."
- **Search your own library.** With
  [semantic search](../../features/semantic-search/) on, "what have I read about
  deliberate practice?" searches your own highlights, notes and digests.
- **Turn reading into cards.** Ask for [flashcard](../../features/flashcards/)
  suggestions from a chapter, a highlight or a note, then create the ones worth
  keeping.
- **Look at your reading over time.** "Which topics in this book did I
  highlight on each reread?"

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

This installs the `crossbill-mcp` command. Your MCP client runs it.

## Configuring

The server needs all three of these environment variables:

| Variable             | What it is                    | Example                 |
| -------------------- | ----------------------------- | ----------------------- |
| `CROSSBILL_URL`      | Base URL of the Crossbill API | `http://localhost:8000` |
| `CROSSBILL_EMAIL`    | The email you registered with | `user@example.com`      |
| `CROSSBILL_PASSWORD` | That account's password       |                         |

The server logs in with these and refreshes its token as needed.

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

To check that the server starts and can log in:

```bash
export CROSSBILL_URL=http://localhost:8000
export CROSSBILL_EMAIL=your-email
export CROSSBILL_PASSWORD=your-password
crossbill-mcp
```

The server uses MCP over stdio, so after it starts it waits for a client.

## Deleting data

Seven tools delete data. Five of them delete things you can create again:
`delete_note`, `delete_flashcard`, `delete_tag`, `delete_tag_group` and
`delete_bookmark`. The other two delete more:

- **`delete_book`** removes a book with all its chapters and highlights. Syncing
  the book from KOReader again recreates it, but the notes, flashcards, tags and
  digests Crossbill kept alongside it are gone.
- **`delete_highlights`** removes highlights from a book with their
  flashcards and bookmarks. Syncing the book again does not restore them. If
  you highlight a passage again on the e-reader, the highlight comes back
  without its flashcards and bookmarks.

Before either of these runs, the server asks you to confirm through MCP
elicitation. The prompt shows what will be deleted: the book's title with its
chapter and highlight counts, or the number of highlights and their book. The
deletion runs only if you confirm. If you decline or close the prompt, nothing
is deleted.

The server shows this prompt itself, so the assistant cannot skip it. If your
MCP client does not support elicitation, the server refuses the deletion and
tells you to use the Crossbill web app.

All seven deletion tools are annotated `destructiveHint: true` (so is
`cancel_job_batch`), and every read-only tool is annotated `readOnlyHint: true`,
so clients can treat them differently. If you allow the whole Crossbill server
in Claude Code, keep a permission prompt for the deletions:

```json
{
  "permissions": {
    "ask": ["mcp__crossbill__delete_*"]
  }
}
```

## Tools that need a provider

Some tools need a provider configured on your Crossbill server. Without it,
they return a message that says what is missing:

- **AI provider** (`AI_PROVIDER`): chapter digest generation and the three
  flashcard-suggestion tools. Without one, they answer that AI features are not
  enabled.
- **Embedding provider** (`EMBEDDING_PROVIDER`): `search_library` and
  `find_related`. Without one, they answer that search is not enabled.

See [Optional components](../../getting-started/optional-components/) for
turning either on.

## Tool reference

The server registers 50 tools. Full descriptions and arguments are in
[`mcp-server/README.md`](https://github.com/Crossbill-App/crossbill-web/blob/main/mcp-server/README.md).

### Books

`list_books`, `get_book`, `get_recent_books`, `set_reading_stage`,
`delete_book`

### Highlights

`get_highlights`, `update_highlight_note`, `tag_highlight`, `untag_highlight`,
`delete_highlights`

### Highlight labels

`get_book_highlight_labels`, `get_global_highlight_labels`,
`update_highlight_label`, `create_global_highlight_label`

### Notes

`create_note`, `get_note`, `get_book_notes`, `update_note`, `delete_note`

`update_note` replaces the whole note and clears any field you leave out. Read
the note with `get_note` first and send back the fields you want to keep.

### Tags

`get_book_tags`, `create_tag`, `update_tag`, `delete_tag`,
`create_or_rename_tag_group`, `delete_tag_group`

### Flashcards

`get_flashcards`, `create_flashcard`, `update_flashcard`, `delete_flashcard`,
`suggest_flashcards_for_chapter`, `suggest_flashcards_for_highlight`,
`suggest_flashcards_for_note`

The three suggestion tools only suggest questions and answers. A card is saved
only when you pass it to `create_flashcard`.

### Chapter digests and background jobs

`get_chapter_digest`, `generate_chapter_digest`, `answer_digest_question`,
`get_book_digests`, `generate_book_digests`, `get_digest_generation_status`,
`get_job_batch`, `cancel_job_batch`

`generate_chapter_digest` makes one AI call and can take tens of seconds.
`generate_book_digests` queues the whole book as a job batch for the
[background worker](../../getting-started/optional-components/#background-worker). Check its
progress with `get_digest_generation_status`.

### Bookmarks

`list_bookmarks`, `create_bookmark`, `delete_bookmark`

### Reading

`get_reading_sessions`, `get_chapter_content`

### Search

`search_library`, `find_related`

### Reflection

`get_book_reflection`, `update_book_reflection`

`update_book_reflection` replaces the whole reflection, like `update_note`.
