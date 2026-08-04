---
title: Installation
description: Run Crossbill with the sample docker compose setup, then install the KOReader plugin on your e-reader.
---

The easiest way to install and run Crossbill is with the sample
`docker-compose.yml` at the top level of the
[crossbill-web repository](https://github.com/Crossbill-Highlights/crossbill-web).
It runs the published Docker image,
[`tumetsu/crossbill`](https://hub.docker.com/r/tumetsu/crossbill), together with
a PostgreSQL database.

## 1. Configure the environment

Copy the example environment file to the project root and fill in your values:

```bash
cp .env.example .env
# Edit .env with your configuration
```

## 2. Start the services

```bash
docker compose up
```

## 3. Install the KOReader plugin

Then install the KOReader
[plugin on your e-reader](https://github.com/Crossbill-Highlights/koreader-plugin).
It is what sends your highlights to Crossbill; without it, Crossbill has nothing
to show. See [KOReader plugin](../koreader-plugin/) for what the plugin syncs.

## 4. Create your account

Crossbill is multi-user: open the web frontend in a browser, register an
account, and everything you sync afterwards belongs to it.

## What's next

- Turn on the extras you want — the background worker for AI or S3-compatible
  storage: [Optional components](../optional-components/).
- Find out what the API offers: the interactive documentation is served at
  `<backend host>/api/v1/docs` while the backend is running.
- Running Crossbill from source instead? Each component has its own development
  instructions, in `backend/README.md` and `frontend/README.md` in the
  repository.
