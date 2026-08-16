---
title: KOReader plugin
description: What the KOReader plugin syncs between your e-reader and Crossbill, and where to find its install instructions.
---

Crossbill gets its content from your e-reader. The
[KOReader plugin](https://github.com/Crossbill-App/koreader-plugin) runs
inside KOReader on the device and talks to your Crossbill server.

## What it syncs

Upwards, from the e-reader to Crossbill:

- **Highlights** — the passages you marked while reading, with where they sit in
  the book, any note you typed about one on the device, and which device it came
  from. Re-syncing a book you have synced before does not create duplicates.
- **Highlight styles** — the highlighter appearance you used: a colour, a
  drawing style, or both. Crossbill keeps them so you can give each one a
  [label](../../features/tags-and-organization/) later.
- **Reading sessions** — the stretches of reading KOReader recorded: when each
  one started and ended, and how far through the book it ran.

Downwards, from Crossbill to the e-reader:

- **Chapter digests** — the plugin can pull generated digests back down so you
  can read a chapter's summary and key points on the device itself.
- **Highlights** — from the plugin menu you can pull the highlights of the book
  you have open. Crossbill holds the master copy, so its set replaces the one on
  the device: highlights you deleted in Crossbill disappear from the device and
  do not come back the next time you sync upwards. Page bookmarks are left as
  they are, and the plugin backs up the book's sidecar file before it writes. A
  highlight with no recorded position — a few very old ones — cannot be placed
  in the text, so it is skipped and reported.

## Installing it

The plugin has its own installation instructions, kept with the plugin so they
stay current with KOReader:

- [Crossbill-App/koreader-plugin](https://github.com/Crossbill-App/koreader-plugin)

In outline, you copy the plugin folder into KOReader's `plugins` directory on
the device, restart KOReader, and point the plugin at your Crossbill server's
address with your account credentials. Follow the plugin repository's README for
the exact steps for your device.

## After the first sync

Once a book has synced, open it in the web frontend. You will find its chapters,
its highlights grouped by chapter, and its reading sessions — everything else
in Crossbill builds on those.
