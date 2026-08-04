---
title: Introduction
description: What Crossbill is, the active-reading ideas behind it, and the components it is made of.
---

Crossbill is a self-hosted reading companion. It collects the passages you
marked on your e-reader and gives you the tools to work them into
understanding, rather than leaving them in a file you never open again.

## The idea

Crossbill borrows its shape from Mortimer J. Adler's _How to Read a Book_.

- **Skimming** comes first: find out what a chapter contains before you read it
  properly. A **chapter digest** — an AI-made summary, key points and
  comprehension questions — is there to support exactly that, and works just as
  well as review afterwards.
- **Coming to terms with the author** happens while you read: you tag
  highlights, and you write **notes** about the terms, characters and concepts
  that carry the argument.
- **Reflection** comes last: a **book reflection** is your answers to Adler's
  four analytical questions about one book, each answer a note of its own.

Alongside that, **flashcards** made from highlights, chapters and notes let you
keep what you read, and a **reading stage** on each book records where you have
got to — you set it by hand; Crossbill never guesses it.

## The components

- **Backend API** — a FastAPI server with a PostgreSQL database. It holds your
  library and serves both the web frontend and the plugins.
- **Web frontend** — the React interface where you browse, edit and organize
  everything.
- **[KOReader plugin](https://github.com/Crossbill-App/koreader-plugin)**
  — runs on your e-reader and syncs highlights up to Crossbill.
- **[Obsidian plugin](https://github.com/Crossbill-App/obsidian-plugin)**
  and **[Anki add-on](https://github.com/Crossbill-App/anki-addon)** —
  optional bridges to the tools you may already use for notes and study.

Two more services are optional: a **background worker** for long-running AI
jobs, and **S3-compatible storage** when the app and the worker cannot share a
filesystem. See [Optional components](../optional-components/).

Ready to run it? Start with [Installation](../installation/).
