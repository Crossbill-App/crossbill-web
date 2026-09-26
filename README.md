<p align="center">
<img width="96" height="96" alt="image" src="https://github.com/user-attachments/assets/6f167cf7-6de3-43d2-85bb-891d57b7be61" />

</p>



# Crossbill

[![CI](https://github.com/Tumetsu/Crossbill/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Tumetsu/Crossbill/actions/workflows/ci.yml)
[![Docker Image Version](https://img.shields.io/docker/v/tumetsu/crossbill?sort=semver)](https://hub.docker.com/r/tumetsu/crossbill)

A self-hosted reading companion web app for guiding your reading process into more active activity. Create summaries of chapters for skimming, manage and organize your highlights, create flash cards and create notes from them. Inspired by [Mortimer J. Adler's How to read a Book](https://www.goodreads.com/book/show/567610.How_to_Read_a_Book)'s ideas on how to encourage more active reading practices for elevated understanding.

Syncs data from e-readers using KOReader, or upload your EPUB files and read them in the built-in web reader — no e-reader needed.

[Read docs](https://crossbill-app.github.io/crossbill-web/)

## Features
- Upload EPUB files from the browser and read them in the web reader - KOReader is optional
- Sync highlights from KOReader with automatic deduplication
- Organize highlights
- Read your books in the browser - jump from a highlight to its place in the book, and make highlights that sync back to KOReader if you use it
- Create flash cards from your highlights and sync them to Anki or get AI suggestions from highlights.
- Create AI summaries from epub book chapters for review and skimming. Ollama, OpenAI, Anthropic and Gemini supported.
- Create notes and link them to the highlights, chapters etc.
- Semantic search over highlights, notes and chapter summaries - find them by meaning instead of exact words, across books and languages. Optional, requires an embedding provider (Ollama or OpenRouter).
- Browse a book by its own chapter structure and track what you have read chapter by chapter
- Reading statistics from your reading sessions in the web reader and KOReader - streaks, days read and total time read
- Supporting features to reflect on the books you have read
- Self-hosted - your data stays on your server
- Multi-user support

## Screenshots

<p align="center">
  <img alt="Crossbill's home page: a row of recent book covers, a year of reading activity drawn as a heat map, and a timeline of the newest highlights and notes." src="site/src/assets/screenshots/landing-page.png" />
  <br />
  <em>Home &mdash; what you are reading now, a year of reading activity, and the highlights and notes you added most recently.</em>
</p>

<table>
  <tr>
    <td width="33%" valign="top">
      <a href="site/src/assets/screenshots/highlights-page.png"><img alt="A book's highlights page: highlights grouped under their chapter headings, each with a date, page number and tag, with tag groups in the left sidebar and a chapter list on the right." src="site/src/assets/screenshots/highlights-page.png" /></a>
      <br />
      <em>Every highlight from a book, grouped by chapter and filterable by tag, date or highlight style.</em>
    </td>
    <td width="33%" valign="top">
      <a href="site/src/assets/screenshots/structure-page.png"><img alt="A book's structure page: the table of contents as a nested tree, each chapter marked read, reading or unread, with a one-line gist and counts of its highlights and notes." src="site/src/assets/screenshots/structure-page.png" /></a>
      <br />
      <em>The book's structure &mdash; what you have read, a one-line gist per chapter, and what you attached to each.</em>
    </td>
    <td width="33%" valign="top">
      <a href="site/src/assets/screenshots/chapter-details.png"><img alt="A chapter dialog: a gist, a generated chapter summary with key points, and comprehension questions with the reader's own written answers below each." src="site/src/assets/screenshots/chapter-details.png" /></a>
      <br />
      <em>A chapter digest &mdash; summary, key points and questions to think about, with room to answer them.</em>
    </td>
  </tr>
</table>

<p align="center">
  <img alt="The web reader showing chapter X of Frankenstein in the browser: two passages highlighted in place, one in pink and one in orange, the book's title and a contents button in the top bar, page-turn arrows at either edge, and pages left in the chapter and percent read in the footer." src="site/src/assets/screenshots/web-reader.png" />
  <br />
  <em>The web reader &mdash; the book itself, with your highlights drawn in place in the colours you gave them.</em>
</p>

## Overview of software components

- **Backend API**: FastAPI server with PostgreSQL database
- **Web Frontend**: Modern React interface for browsing, editing, and organizing your highlights
- **[KOReader Plugin](https://github.com/Crossbill-App/koreader-plugin)** (optional): Syncs highlights directly from your KOReader e-reader
- **[Obsidian Plugin](https://github.com/Crossbill-App/obsidian-plugin)**: Integrate highlights into your Obsidian notes
- [**Anki Plugin**](https://github.com/Crossbill-App/anki-addon): Integrate highlights into your Anki flash cards

## Installation

Easiest way to install and run Crossbill is by using sample `docker-compose.yml` on top level of this repository.

1. Copy the example environment file to the project root and fill in your values:

```bash
cp .env.example .env
# Edit .env with your configuration
```

2. Then start the services:

```bash
docker compose up
```

Then add your books in one of two ways:

- **Upload EPUBs in the browser.** Use the upload button on the Library page, then read and highlight the book in the web reader. No e-reader needed.
- **Sync from KOReader.** Install the KOReader [plugin on your e-reader](https://github.com/Crossbill-App/koreader-plugin).

You can use both. A book you upload is the same book the plugin finds when it later syncs it.

### Background Worker

The `docker-compose.yml` includes an optional `worker` service that processes background jobs (e.g., batch AI digest generation for book chapters). It uses the same Docker image as the main app with a different entrypoint.

The worker requires AI provider configuration (`AI_PROVIDER`, API keys) to process AI-related tasks. You can adjust concurrency via `WORKER_CONCURRENCY` (default: 5).

For development, run the worker separately:

```bash
make dev-worker
```

### Semantic Search (Optional)

Semantic search embeds notes, highlights and chapter digests into a pgvector
index so related content surfaces across books and languages. It is off unless
an embedding provider is configured.

```
# Local development, via Ollama
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL_NAME=bge-m3
EMBEDDING_BASE_URL=http://localhost:11434/v1

# Hosted, via OpenRouter (reuses OPENROUTER_API_KEY)
EMBEDDING_PROVIDER=openrouter
EMBEDDING_MODEL_NAME=baai/bge-m3
```

`EMBEDDING_BASE_URL` is required for `ollama` and optional for `openrouter`
(defaults to `https://openrouter.ai/api/v1`). `EMBEDDING_MODEL_VERSION`
(default `1`) is stored with every vector: bump it to force a re-embed on the
next backfill without a schema change.

The vector width is fixed at 1024 (bge-m3) by the database column, so switching
to a model of a different dimension is a migration plus a full re-embed, not a
setting. Postgres must have the `vector` extension available, **version 0.8 or
newer** — search sets `hnsw.iterative_scan`, without which a query can come back
empty once one user's vectors sit nearer the index than another's. The bundled
`pgvector/pgvector:pg18` image ships 0.8.6.

Embeddings are written by background jobs. Existing content is indexed by
`POST /api/v1/semantic/backfill`, which also prunes entries whose source is
gone; progress is visible through the usual job-batch views.

### S3-Compatible Storage (Optional)

By default, Crossbill stores ebook files and covers on the local filesystem. For multi-container deployments (e.g., Railway) where the app and worker containers cannot share a filesystem, you can configure S3-compatible storage so both containers access the same files.

Set these environment variables to enable S3 storage:

```
S3_ENDPOINT_URL=https://your-s3-endpoint.example.com
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=crossbill-files
S3_REGION=your-region
```

When these are set, Crossbill automatically uses S3 instead of local disk. When they are not set, local file storage is used (the `book-files` volume mount).

For local development or self-hosted server, you can use [Garage](https://garagehq.deuxfleurs.fr/) as an S3-compatible server. The `docker-compose.yml` includes an optional `garage` service. 
Start it and run the one-time setup script:

```bash
docker compose up -d garage
./scripts/setup_garage.sh

# After setting the environment variables restart containers if they are already running:
docker restart crossbill-app crossbill-worker
```

The script creates the bucket and API key, then prints the credentials to add to your `.env`. If you are going to use Garage in production, please refer [their docs](https://garagehq.deuxfleurs.fr/)
for proper settings to be set in the `garage.toml`!

## Development

Each component has its own installation instructions for development:

- **Backend**: See [backend/README.md](backend/README.md)
- **Frontend**: See [frontend/README.md](frontend/README.md)

API documentation can be found from URL `<backend host>/api/v1/docs` when running the backend server.

## Contributions

Contributions are welcome. Few guide lines:

- Check if there is an issue you would like to work on and comment on it to discuss
- Add first issue about the feature etc. you'd like to see in the application (and work on if possible!)
- AI-assisted coding is welcome as long as you review your contributions before submitting them to the review.
