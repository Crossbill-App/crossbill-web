---
title: Installation
description: Run Crossbill with the sample docker compose setup, create an account, and add your books by uploading EPUBs or syncing from KOReader.
---

The easiest way to install and run Crossbill is with the sample
`docker-compose.yml` at the top level of the
[crossbill-web repository](https://github.com/Crossbill-App/crossbill-web).
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

## 3. Create your account

Crossbill is multi-user: open the web frontend in a browser, register an
account, and every book you add afterwards belongs to it.

## 4. Add your books

There are two ways in. You can use either one, or both.

- **Upload an EPUB.** On the **Library** page, use the upload button in the
  bottom-right corner and pick an EPUB file. The book opens once it is in, and
  you can read and highlight it in the [web reader](../../features/web-reader/).
  You do not need an e-reader.
- **Sync from KOReader.** Install the KOReader
  [plugin on your e-reader](https://github.com/Crossbill-App/koreader-plugin)
  and sync. See [KOReader plugin](../koreader-plugin/) for what the plugin
  syncs.

If you upload a book and later sync the same EPUB from KOReader, the plugin
finds the uploaded book instead of adding a second copy.

## Serving the web reader

The [web reader](../../features/web-reader/) loads a book's files with a
short-lived cookie, `publication_access`, instead of the login token. Most
installs need nothing extra. Behind a reverse proxy, check these:

- **One origin.** Serve the frontend and `/api` from the same origin, as the
  Docker image does. Do not rewrite the `/api/v1` path: each book's cookie is
  scoped to `/api/v1/readium/books/<id>/`.
- **`PUBLIC_BASE_URL`** must be the address browsers use, such as
  `https://crossbill.example.com`. The book's manifest builds its links from
  it. Production refuses to start without it.
- **HTTPS, with `COOKIE_SECURE=true`.** Safari treats a chapter's images as
  cross-site requests, so the cookie must be `SameSite=None`, and browsers
  accept that only on a `Secure` cookie. With `COOKIE_SECURE=false`, the cookie
  falls back to `SameSite=Lax`: other browsers still read the book, Safari
  shows broken images.

| Symptom                                                                | Likely cause                                                                   |
|------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| The book's text shows but its images are broken, in Safari only        | Served over plain HTTP, or `COOKIE_SECURE=false`                               |
| Every book fails to open; requests under `/api/v1/readium/` answer 401 | The proxy rewrites the `/api` path, or serves the frontend from another origin |
| Chapters fail to load; the manifest's links point at an internal host  | `PUBLIC_BASE_URL` is unset or wrong                                            |

## What's next

- Turn on the extras you want — the background worker for AI or S3-compatible
  storage: [Optional components](../optional-components/).
- Find out what the API offers: the interactive documentation is served at
  `<backend host>/api/v1/docs` while the backend is running.
- Running Crossbill from source instead? Each component has its own development
  instructions, in `backend/README.md` and `frontend/README.md` in the
  repository.
