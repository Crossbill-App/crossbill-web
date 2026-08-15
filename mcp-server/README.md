# Crossbill MCP Server

Model Context Protocol (MCP) server that exposes the Crossbill reading companion's REST API to AI assistants like Claude.

## Features

- Browse and search your book library
- Read chapter content from EPUB files
- Search and annotate highlights
- Tag highlights
- Create, update, and delete flashcards
- Manage bookmarks
- View reading sessions
- Semantic search over highlights, notes, and chapter digests

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
- **create_flashcard** - Create a flashcard, optionally linked to a highlight
- **update_flashcard** - Update a flashcard's question and/or answer
- **delete_flashcard** - Delete a flashcard

### Reading

- **get_reading_sessions** - Get reading sessions for a book
- **get_chapter_content** - Get full text content of a chapter from the EPUB

### Bookmarks

- **create_bookmark** - Bookmark a highlight
- **delete_bookmark** - Delete a bookmark

### Semantic Search

Requires an embedding provider configured on the Crossbill server; without one, both tools report that semantic search is not enabled.

- **semantic_search** - Rank highlights, notes, and chapter digests by semantic similarity to a natural-language query, optionally scoped to one book. Results are grouped by content type, with `limit` applied per group.
- **find_related** - Find content similar to an existing item, named by `content_type` (`note`, `highlight`, or `digest`) and `content_id`. Same grouped response shape as `semantic_search`.
