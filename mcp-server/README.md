# Crossbill MCP Server

Model Context Protocol (MCP) server that exposes the Crossbill reading companion's REST API to AI assistants like Claude.

## Features

- Browse and search your book library
- Read chapter content from EPUB files
- Search and annotate highlights
- Tag highlights, and manage a book's tags and tag groups
- Create, update, and delete flashcards
- Manage bookmarks
- View reading sessions and their AI summaries
- Track a book's reading stage and its four-question reflection
- Semantic search over highlights, notes, and chapter digests
- Create, read, update, and delete markdown notes
- Generate chapter digests and AI flashcard suggestions

## Installation

```bash
cd mcp-server
pip install -e .
```

## Configuration

Set the following environment variables:

| Variable             | Description                   | Example                 |
| -------------------- | ----------------------------- | ----------------------- |
| `CROSSBILL_URL`      | Base URL of the Crossbill API | `http://localhost:8000` |
| `CROSSBILL_EMAIL`    | Login email                   | `user@example.com`      |
| `CROSSBILL_PASSWORD` | Login password                |                         |

## Usage

### Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

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

Add to your Claude Code MCP settings:

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

Can also be added by command:

```
claude mcp add crossbill -e CROSSBILL_URL=http://localhost:8000 -e CROSSBILL_EMAIL=user@example.com -e CROSSBILL_PASSWORD='password' -- crossbill-mcp
```

### Direct

```bash
export CROSSBILL_URL=http://localhost:8000
export CROSSBILL_EMAIL=your-email
export CROSSBILL_PASSWORD=your-password
crossbill-mcp
```

## Available Tools

### Books

- **list_books** - List books with optional search and pagination
- **get_book** - Get detailed book info with chapters and highlights
- **get_recently_viewed_books** - Get recently viewed books
- **set_reading_stage** - Set a book's manual reading stage (`to_read`, `skimming`, `reading`, `finished`, `reflected`), or clear it back to the stage Crossbill infers from reading activity

### Highlights

- **get_highlights** - Get highlights from a book, optionally filtered by search
- **update_highlight_note** - Add or update a note on a highlight
- **tag_highlight** - Add a tag to a highlight
- **untag_highlight** - Remove a tag from a highlight

### Highlight Labels

- **get_book_highlight_labels** - Get all highlight labels for a book with resolved labels and counts
- **get_global_highlight_labels** - Get all global default highlight labels
- **update_highlight_label** - Update label text and/or UI color on a highlight style
- **create_global_highlight_label** - Create a new global default highlight label

### Flashcards

- **get_flashcards** - Get all flashcards for a book
- **create_flashcard** - Create a flashcard, optionally anchored to a `highlight_id`, `note_id`, or `chapter_id` (give at most one)
- **update_flashcard** - Update a flashcard's question and/or answer
- **delete_flashcard** - Delete a flashcard

The three suggestion tools below require an AI provider configured on the Crossbill server; without one they report that AI features are not enabled. They only suggest question/answer pairs — nothing is saved until you pass one to `create_flashcard`.

- **suggest_flashcards_for_chapter** - Suggest flashcards from a chapter's digest (the chapter must already have one)
- **suggest_flashcards_for_highlight** - Suggest flashcards from a highlight's text
- **suggest_flashcards_for_note** - Suggest flashcards from a note and its linked highlights

### Reading

- **get_reading_sessions** - Get reading sessions for a book
- **get_chapter_content** - Get full text content of a chapter from the EPUB
- **get_reading_session_summary** - Get an AI summary of what was read in one session, cached after the first call. Requires an AI provider configured on the Crossbill server

### Chapter Digests

A digest is an AI-written study aid for one chapter: a summary, a list of keypoints, and comprehension questions with answers. Generating one requires an AI provider configured on the Crossbill server; without one, `generate_chapter_digest` and `generate_book_digests` report that AI features are not enabled.

- **get_chapter_digest** - Get a chapter's existing digest, or a note that it has none yet
- **generate_chapter_digest** - Generate one chapter's digest synchronously; this makes an AI call and can take tens of seconds
- **answer_digest_question** - Record the user's answer to one question, by its zero-based index into the digest's questions
- **get_book_digests** - Get every chapter digest a book has
- **generate_book_digests** - Enqueue digest generation for all of a book's chapters as a background job batch
- **get_digest_generation_status** - Get the active digest batch for a book, for polling progress
- **get_job_batch** - Get any job batch by ID, with its status and progress counts
- **cancel_job_batch** - Cancel a job batch and abort the jobs in it that have not run yet

### Bookmarks

- **create_bookmark** - Bookmark a highlight
- **delete_bookmark** - Delete a bookmark

### Semantic Search

Requires an embedding provider configured on the Crossbill server; without one, both tools report that semantic search is not enabled.

- **semantic_search** - Rank highlights, notes, and chapter digests by semantic similarity to a natural-language query, optionally scoped to one book. Results are grouped by content type, with `limit` applied per group.
- **find_related** - Find content similar to an existing item, named by `content_type` (`note`, `highlight`, or `digest`) and `content_id`. Same grouped response shape as `semantic_search`.

### Notes

Notes are markdown documents that belong to a book and can be linked to that book's chapters and highlights, and to tags. A note may carry an optional `kind`: `character`, `term`, `concept`, `gist`, `reflection`, or `other`.

- **create_note** - Create a note in a book from a title and markdown body, optionally with a kind and links to chapters, highlights, and tags
- **get_note** - Get one note with its linked chapters, highlights, tags, and flashcards
- **get_book_notes** - List a book's notes, optionally filtered by `kind`, `chapter_id`, `highlight_id`, or `tag_id` (filters combine)
- **update_note** - Replace a note's fields and links in full. Anything omitted is cleared, so fetch the note with `get_note` first and resend everything you want to keep
- **delete_note** - Delete a note and its links

### Tags

Tags belong to one book and can be attached to that book's highlights and notes. A tag group is an optional folder gathering related tags; a tag outside every group has a null `tag_group_id`.

- **get_book_tags** - Get every tag of a book, with the group each one belongs to
- **create_tag** - Create a tag in a book (to tag a highlight, use `tag_highlight`, which creates the tag by name when needed)
- **update_tag** - Rename a tag and/or move it into a tag group
- **delete_tag** - Delete a tag, which also removes it from every highlight carrying it
- **create_or_rename_tag_group** - Create a tag group, or rename an existing one by passing its `tag_group_id`
- **delete_tag_group** - Delete a tag group, leaving the tags in it ungrouped

### Reflection

A book's reflection is its answers to four fixed questions: what is it about, what does it say, do I agree, so what. An answer is not text but a reference to the note holding that answer's markdown, so answering means writing a note first and passing its ID. The reflection also links the book's term and concept notes.

- **get_book_reflection** - Get a book's reflection; every book has one, unanswered questions are null
- **update_book_reflection** - Replace a reflection in full. Anything omitted is cleared, so fetch it with `get_book_reflection` first and resend everything you want to keep
