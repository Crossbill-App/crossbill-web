---
title: Optional components
description: The background worker and S3-compatible storage — what each one adds and how to configure it.
---

Crossbill runs without any of these. Turn on the ones you want.

## Background worker

The `docker-compose.yml` includes an optional `worker` service that processes
background jobs (e.g. batch AI digest generation for book chapters). It uses the
same Docker image as the main app with a different entrypoint.

The worker requires AI provider configuration (`AI_PROVIDER`, API keys) to
process AI-related tasks. You can adjust concurrency via `WORKER_CONCURRENCY`
(default: 5). It is also what writes the embeddings behind
[semantic search](../../features/semantic-search/).

For development, run the worker separately:

```bash
make dev-worker
```

## Semantic search

Searching highlights, notes and chapter digests by meaning is off unless an
embedding provider is configured. It also needs the background worker above and
a PostgreSQL with pgvector 0.8 or newer — the `docker-compose.yml` database
image already has it. The environment variables are in
[Semantic search](../../features/semantic-search/#turning-it-on).

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
