---
title: Optional components
description: What the background worker and S3-compatible storage add, and how to configure them.
---

Crossbill runs without these components. Add the ones you need.

## Background worker

The `docker-compose.yml` includes an optional `worker` service that runs
background jobs. Examples are generating chapter digests for a whole book and
writing the embeddings for [semantic search](../../features/semantic-search/).
The worker uses the same Docker image as the main app with a different
entrypoint.

For AI jobs, the worker needs an AI provider (`AI_PROVIDER` and its API key).
Set the number of parallel jobs with `WORKER_CONCURRENCY` (default: 5).

For development, run the worker separately:

```bash
make dev-worker
```

## Semantic search

Semantic search needs three things:

- an embedding provider
- the background worker
- PostgreSQL with pgvector 0.8 or newer. The database image in
  `docker-compose.yml` includes it.
Semantic search is off until you set an embedding provider. The environment
variables are in [Semantic search](../../features/semantic-search/#turning-it-on).

## S3-compatible storage

By default, Crossbill stores ebook files and covers on the local filesystem.
If the app and worker containers cannot share a filesystem, for example on
Railway, use S3-compatible storage so both containers can read the same files.

To use S3 storage, set these environment variables:

```
S3_ENDPOINT_URL=https://your-s3-endpoint.example.com
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=crossbill-files
S3_REGION=your-region
```

When these are set, Crossbill uses S3. Otherwise it stores files in the
`book-files` volume.

For local development or a self-hosted server, you can use
[Garage](https://garagehq.deuxfleurs.fr/) as the S3-compatible server. The
`docker-compose.yml` includes an optional `garage` service. Start it and run the
one-time setup script:

```bash
docker compose up -d garage
./scripts/setup_garage.sh

# After setting the environment variables restart containers if they are already running:
docker restart crossbill-app crossbill-worker
```

The script creates the bucket and API key, then prints the credentials to add to
your `.env`. To run Garage in production, see the
[Garage documentation](https://garagehq.deuxfleurs.fr/) for the `garage.toml`
settings.
