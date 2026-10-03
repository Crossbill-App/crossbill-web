<p align="center">
<img width="96" height="96" alt="image" src="https://github.com/user-attachments/assets/6f167cf7-6de3-43d2-85bb-891d57b7be61" />

</p>



# Crossbill

[![CI](https://github.com/Tumetsu/Crossbill/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Tumetsu/Crossbill/actions/workflows/ci.yml)
[![Docker Image Version](https://img.shields.io/docker/v/tumetsu/crossbill?sort=semver)](https://hub.docker.com/r/tumetsu/crossbill)

A self-hosted reading companion web app that helps you read more actively. Generate chapter summaries for skimming, organize your highlights, and make flashcards and notes from them. Inspired by the active reading method in [Mortimer J. Adler's How to Read a Book](https://www.goodreads.com/book/show/567610.How_to_Read_a_Book).

Read EPUBs in the built-in web reader, or sync highlights from an e-reader with KOReader.

[Read docs](https://crossbill-app.github.io/crossbill-web/)

## Features
- Upload EPUB files and read them in the web reader. KOReader is optional.
- Sync highlights from KOReader with automatic deduplication
- Organize highlights
- Jump from a highlight to its place in the book in the web reader, and make highlights that sync back to KOReader
- Create flash cards from your highlights and sync them to Anki or get AI suggestions from highlights.
- Create AI summaries from epub book chapters for review and skimming. Ollama, OpenAI, Anthropic and Gemini supported.
- Create notes and link them to the highlights, chapters etc.
- Semantic search over highlights, notes and chapter summaries. Finds them by meaning, across books and languages. Optional, requires an embedding provider (Ollama or OpenRouter).
- Browse a book by its own chapter structure and track what you have read chapter by chapter
- Reading statistics from your reading sessions in the web reader and KOReader: streaks, days read and total time read
- Book reflections based on Adler's four analytical-reading questions
- Self-hosted, so your data stays on your server
- Multi-user support

## Screenshots

<p align="center">
  <img alt="Crossbill's home page: a row of recent book covers, a year of reading activity drawn as a heat map, and a timeline of the newest highlights and notes." src="site/src/assets/screenshots/landing-page.png" />
  <br />
  <em>Home: the books you are reading, a year of reading activity, and your latest highlights and notes.</em>
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
      <em>The book's structure: what you have read, a one-line gist per chapter, and the highlights and notes of each chapter.</em>
    </td>
    <td width="33%" valign="top">
      <a href="site/src/assets/screenshots/chapter-details.png"><img alt="A chapter dialog: a gist, a generated chapter summary with key points, and comprehension questions with the reader's own written answers below each." src="site/src/assets/screenshots/chapter-details.png" /></a>
      <br />
      <em>A chapter digest: summary, key points and questions to think about, with your answers.</em>
    </td>
  </tr>
</table>

<p align="center">
  <img alt="The web reader showing chapter X of Frankenstein in the browser: two passages highlighted in place, one in pink and one in orange, the book's title and a contents button in the top bar, page-turn arrows at either edge, and pages left in the chapter and percent read in the footer." src="site/src/assets/screenshots/web-reader.png" />
  <br />
  <em>The web reader shows your highlights in their colours.</em>
</p>

## Overview of software components

- **Backend API**: FastAPI server with PostgreSQL database
- **Web Frontend**: React app for browsing, editing and organizing your highlights
- **[KOReader Plugin](https://github.com/Crossbill-App/koreader-plugin)** (optional): Syncs highlights directly from your KOReader e-reader
- **[Obsidian Plugin](https://github.com/Crossbill-App/obsidian-plugin)**: Integrate highlights into your Obsidian notes
- [**Anki Plugin**](https://github.com/Crossbill-App/anki-addon): Integrate highlights into your Anki flash cards

## Installation

The easiest way to run Crossbill is with the sample `docker-compose.yml` at the top level of this repository.

1. Copy the example environment file to the project root and fill in your values:

```bash
cp .env.example .env
# Edit .env with your configuration
```

2. Then start the services:

```bash
docker compose up
```

Then add your books. You can use one or both of these:

- **Upload EPUBs in the browser.** Use the upload button on the Library page, then read and highlight the book in the web reader.
- **Sync from KOReader.** Install the KOReader [plugin on your e-reader](https://github.com/Crossbill-App/koreader-plugin).

If you upload a book and later sync the same EPUB from KOReader, the plugin adds to the uploaded book.

### Background Worker

The `docker-compose.yml` includes an optional `worker` service that runs background jobs, such as generating chapter digests for a whole book. It uses the same Docker image as the main app with a different entrypoint.

For AI jobs, the worker needs an AI provider (`AI_PROVIDER` and its API key). Set the number of parallel jobs with `WORKER_CONCURRENCY` (default: 5).

For development, run the worker separately:

```bash
make dev-worker
```

### Semantic Search (Optional)

Semantic search stores embeddings of notes, highlights and chapter digests in a
pgvector index, so you can find related content across books and languages. It
is off until you set an embedding provider.

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
(default `1`) is stored with every vector. Increase it to re-embed everything on
the next backfill without a schema change.

The database column fixes the vector width at 1024, the size `bge-m3` produces.
Switching to a model with a different size requires a migration and a full
re-embed.

Postgres needs the `vector` extension, **version 0.8 or newer**. Search uses
`hnsw.iterative_scan`. Without it, a query can return no results when another
user's vectors are closer in the index. The bundled `pgvector/pgvector:pg18`
image includes 0.8.6.

Background jobs write the embeddings. To index existing content, call
`POST /api/v1/semantic/backfill`. It also removes entries whose source was
deleted. You can follow its progress in the job-batch views.

### S3-Compatible Storage (Optional)

By default, Crossbill stores ebook files and covers on the local filesystem. If the app and worker containers cannot share a filesystem, for example on Railway, use S3-compatible storage so both containers can read the same files.

To use S3 storage, set these environment variables:

```
S3_ENDPOINT_URL=https://your-s3-endpoint.example.com
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=crossbill-files
S3_REGION=your-region
```

When these are set, Crossbill uses S3. Otherwise it stores files in the `book-files` volume.

For local development or a self-hosted server, you can use [Garage](https://garagehq.deuxfleurs.fr/) as the S3-compatible server. The `docker-compose.yml` includes an optional `garage` service. Start it and run the one-time setup script:

```bash
docker compose up -d garage
./scripts/setup_garage.sh

# After setting the environment variables restart containers if they are already running:
docker restart crossbill-app crossbill-worker
```

The script creates the bucket and API key, then prints the credentials to add to your `.env`. To run Garage in production, see the [Garage documentation](https://garagehq.deuxfleurs.fr/) for the `garage.toml` settings.

## Development

Each component has its own installation instructions for development:

- **Backend**: See [backend/README.md](backend/README.md)
- **Frontend**: See [frontend/README.md](frontend/README.md)

The API documentation is at `<backend host>/api/v1/docs` while the backend is running.

## Contributions

Contributions are welcome. Few guide lines:

- Check if there is an issue you would like to work on and comment on it to discuss
- Add first issue about the feature etc. you'd like to see in the application (and work on if possible!)
- AI-assisted coding is welcome as long as you review your contributions before submitting them to the review.
