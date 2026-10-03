---
title: Optional components
description: How the background worker runs, how to turn on semantic search, and how to use S3-compatible storage.
---

Crossbill runs without changing any of these. Change the ones you need.

## Background worker

The background worker runs long jobs, such as generating chapter digests for a
whole book and writing the embeddings for
[semantic search](../../features/semantic-search/).

By default, the app runs the worker in its own process, so you do not need to
set anything up. Use this unless you have a reason not to.

For AI jobs, the worker needs an AI provider (`AI_PROVIDER` and its API key).
Set the number of jobs it runs at the same time with `WORKER_CONCURRENCY`
(default: 2).

### Running the worker in a separate container

To run the worker in its own container, for example to scale it separately
from the app:

1. Uncomment the `worker` service in `docker-compose.yml`.
2. Set `EMBEDDED_WORKER=false` in `.env`.
3. Run `docker compose up -d`.

The worker container uses the same image and `.env` as the app. If you store
book files on local disk, give it the same volume as the app. If the two
containers cannot share a folder, use
[S3-compatible storage](#s3-compatible-storage).

For development, run the worker separately with:

```bash
make dev-worker
```

## Semantic search

Semantic search needs:

- an embedding provider
- PostgreSQL with pgvector 0.8 or newer. The database image in
  `docker-compose.yml` includes it.

Semantic search is off until you set an embedding provider. The environment
variables are in [Semantic search](../../features/semantic-search/#turning-it-on).

## S3-compatible storage

By default, Crossbill stores ebook files and covers on the local filesystem.
If the app and worker containers cannot share a filesystem, for example on
Railway, use S3-compatible storage so both containers can read the same files.

To use S3 storage, set these environment variables in `.env`:

```
S3_ENDPOINT_URL=https://your-s3-endpoint.example.com
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=crossbill-files
S3_REGION=your-region
```

When these are set, Crossbill uses S3. Otherwise it stores files in the folder
mounted at `/app/book-files`. Files already on local disk are not moved to S3,
so books uploaded before the switch cannot be opened in the web reader.

### Using Garage

For local development or a self-hosted server, you can use
[Garage](https://garagehq.deuxfleurs.fr/) as the S3-compatible server. The
`docker-compose.yml` includes a `garage` service, which starts only when you
name it.

1. Start Garage and run the one-time setup script:

   ```bash
   docker compose up -d garage
   ./scripts/setup_garage.sh
   ```

   The script creates the bucket and an API key, and prints the values to add
   to `.env`.

2. Add the values to `.env`. When Crossbill runs in Docker, use
   `S3_ENDPOINT_URL=http://garage:3900`. When the backend runs on your machine
   for development, use `http://localhost:3900`.

3. Apply the new settings:

   ```bash
   docker compose up -d
   ```

   `docker restart` does not read `.env` again, so use `docker compose up -d`.

Commands that act on all services skip Garage unless you add `--profile s3`.
For example, `docker compose down` leaves Garage running, so stop everything
with:

```bash
docker compose --profile s3 down
```

To run Garage in production, see the
[Garage documentation](https://garagehq.deuxfleurs.fr/) for the `garage.toml`
settings.
