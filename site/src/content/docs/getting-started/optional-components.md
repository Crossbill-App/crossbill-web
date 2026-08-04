---
title: Optional components
description: The background worker, semantic search and S3-compatible storage — what each one adds and how to configure it.
---

Crossbill runs without any of these. Turn on the ones you want.

## Background worker

The `docker-compose.yml` includes an optional `worker` service that processes
background jobs (e.g. batch AI digest generation for book chapters). It uses the
same Docker image as the main app with a different entrypoint.

The worker requires AI provider configuration (`AI_PROVIDER`, API keys) to
process AI-related tasks. You can adjust concurrency via `WORKER_CONCURRENCY`
(default: 5).

For development, run the worker separately:

```bash
make dev-worker
```

## Semantic search

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

## S3-compatible storage

By default, Crossbill stores ebook files and covers on the local filesystem. For
multi-container deployments (e.g. Railway) where the app and worker containers
cannot share a filesystem, you can configure S3-compatible storage so both
containers access the same files.

Set these environment variables to enable S3 storage:

```
S3_ENDPOINT_URL=https://your-s3-endpoint.example.com
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=crossbill-files
S3_REGION=your-region
```

When these are set, Crossbill automatically uses S3 instead of local disk. When
they are not set, local file storage is used (the `book-files` volume mount).

For local development or a self-hosted server, you can use
[Garage](https://garagehq.deuxfleurs.fr/) as an S3-compatible server. The
`docker-compose.yml` includes an optional `garage` service. Start it and run the
one-time setup script:

```bash
docker compose up -d garage
./scripts/setup_garage.sh

# After setting the environment variables restart containers if they are already running:
docker restart crossbill-app crossbill-worker
```

The script creates the bucket and API key, then prints the credentials to add to
your `.env`. If you are going to use Garage in production, refer to
[their docs](https://garagehq.deuxfleurs.fr/) for the settings to put in
`garage.toml`.
