<p align="center">

<img width="96" height="96" alt="image" src="https://github.com/user-attachments/assets/6461072f-2265-443b-a018-db7ae26cb42f" />
</p>

# Crossbill

[![CI](https://github.com/Tumetsu/Crossbill/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Tumetsu/Crossbill/actions/workflows/ci.yml)
[![Docker Image Version](https://img.shields.io/docker/v/tumetsu/crossbill?sort=semver)](https://hub.docker.com/r/tumetsu/crossbill)

A self-hosted reading companion web app for guiding your reading process into more active activity. Create summaries of chapters for skimming, manage and organize your highlights, create flash cards and create notes from them. Inspired by [Mortimer J. Adler's How to read a Book](https://www.goodreads.com/book/show/567610.How_to_Read_a_Book)'s ideas on how to encourage more active reading practices for elevated understanding.

Syncs data from e-readers using Koreader.

## Features
- Sync highlights from KOReader with automatic deduplication
- Organize highlights
- Create flash cards from your highlights and sync them to Anki or get AI suggestions from highlights.
- Create AI summaries from epub book chapters for review and skimming. Ollama, OpenAI, Anthropic and Gemini supported.
- Create notes and link them to the highlights, chapters etc.
- Supporting features to reflect on the books you have read
- Self-hosted - your data stays on your server
- Multi-user support

## Screenshots

<img width="250" alt="image" src="https://github.com/user-attachments/assets/262ba290-ed79-47ff-a8b3-aa6b3f3b59a3" />
<img width="250" alt="image" src="https://github.com/user-attachments/assets/397be7cd-541d-49be-975b-d5db3caab2c3" />
<img width="250" alt="image" src="https://github.com/user-attachments/assets/de548aa4-c721-4ff7-b008-3c6aa8de0bdd" />

## Overview of software components

- **Backend API**: FastAPI server with PostgreSQL database
- **Web Frontend**: Modern React interface for browsing, editing, and organizing your highlights
- **[KOReader Plugin](https://github.com/Crossbill-App/koreader-plugin)**: Syncs highlights directly from your KOReader e-reader
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

Then install the Koreader [plugin on your e-reader](clients/koreader-plugin/crossbill.koplugin/README.md).

### Background Worker

The `docker-compose.yml` includes an optional `worker` service that processes background jobs (e.g., batch AI digest generation for book chapters). It uses the same Docker image as the main app with a different entrypoint.

The worker requires AI provider configuration (`AI_PROVIDER`, API keys) to process AI-related tasks. You can adjust concurrency via `WORKER_CONCURRENCY` (default: 5).

For development, run the worker separately:

```bash
make dev-worker
```

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
