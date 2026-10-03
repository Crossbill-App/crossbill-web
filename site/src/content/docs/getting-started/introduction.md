---
title: Introduction
description: What Crossbill is, the active-reading ideas behind it, and the components it is made of.
---

Crossbill is a self-hosted reading companion. It collects the passages you
highlight, in its own web reader or on your e-reader, and gives you tools to
study them.

You can upload an EPUB, read it in the browser and highlight as you go. If you
read in KOReader, its plugin syncs your highlights to Crossbill.

## The idea

Crossbill follows the reading method in Mortimer J. Adler's _How to Read a
Book_.

- **Skimming**: before you read a chapter properly, find out what it contains.
  A **chapter digest** helps with this. It is an AI-made summary with key
  points and comprehension questions. You can also use it for review after
  reading.
- **Coming to terms with the author**: while you read, you tag highlights and
  write **notes** about the terms, characters and concepts in the book.
- **Reflection**: when you finish, you write a **book reflection**. It holds
  your answers to Adler's four analytical questions about the book. Each answer
  is a note.

**Flashcards** made from highlights, chapters and notes help you remember what
you read. A **reading stage** on each book shows how far you are with it. You
set the stage yourself.

## The components

- **Backend API**: a FastAPI server with a PostgreSQL database. It stores your
  library and serves the web frontend and the plugins.
- **Web frontend**: the React app where you browse and organize your library,
  upload EPUBs and read them in the web reader.
- **[KOReader plugin](https://github.com/Crossbill-App/koreader-plugin)**
  (optional): runs on your e-reader and syncs highlights to Crossbill.
- **[Obsidian plugin](https://github.com/Crossbill-App/obsidian-plugin)** and
  **[Anki add-on](https://github.com/Crossbill-App/anki-addon)** (optional):
  bring your highlights and flashcards into Obsidian and Anki.

Two more services are optional: a **background worker** for long-running AI
jobs, and **S3-compatible storage** for setups where the app and the worker
cannot share a filesystem. See [Optional components](../optional-components/).

To install Crossbill, go to [Installation](../installation/).
