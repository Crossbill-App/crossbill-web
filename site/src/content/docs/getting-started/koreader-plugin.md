---
title: KOReader plugin
description: What the KOReader plugin syncs between your e-reader and Crossbill, and where to find its install instructions.
---

The [KOReader plugin](https://github.com/Crossbill-App/koreader-plugin) syncs
your reading from an e-reader to Crossbill. It runs inside KOReader on the
device and connects to your Crossbill server.

The plugin is optional. Without it, you can upload EPUBs from the **Library**
page and read them in the [web reader](../../features/web-reader/).

## What it syncs

- **Highlights**: the passages you marked, their position in the book, any note
  you typed on the device, and the device they came from.
- **Highlight styles**: the colour and drawing style of each highlight. You can
  give each style a [label](../../features/tags-and-organization/) in
  Crossbill.
- **Reading sessions**: when each reading session started and ended, and how far
  you got in the book.
- **Chapter digests**: the plugin downloads generated digests, so you can read a
  chapter's summary and key points on the device.

If you read the same book on more than one e-reader, the most recent edit to a
highlight's note or colour wins.

## Deleting a highlight

If you delete a highlight on the e-reader:

- Crossbill removes it from all your devices on the next sync.
- The web app keeps it, with its notes, flashcards, tags and bookmarks, and
  marks it **Deleted on the e-reader**.

To delete a highlight from Crossbill and all devices, delete it in the web app.

If a sync would remove every highlight this device has synced for a book, the
plugin asks you first.
This happens when you delete all the highlights, but also when KOReader's
sidecar file for the book is missing. Choose **Keep** to keep the highlights in
Crossbill. The rest of the sync still runs. An automatic background sync does
not ask. It skips the removal and leaves it for your next manual sync.

## Highlighting a passage again

If you highlight a passage you deleted earlier, Crossbill restores the old
highlight instead of creating a new one. What comes back depends on where you
deleted it:

| Deleted on        | Restored with                     |
| ----------------- | --------------------------------- |
| The e-reader      | Tags, flashcards and bookmarks    |
| The web app       | Tags only                         |

Flashcards and bookmarks of a highlight deleted in the web app are deleted for
good.

Restoring works from the second sync of a book on a device. On the first sync,
the plugin cannot tell an old highlight from a new one, so it restores nothing.

## Installing it

The installation steps are in the
[plugin repository](https://github.com/Crossbill-App/koreader-plugin). In short:

1. Copy the plugin folder into KOReader's `plugins` directory on the device.
2. Restart KOReader.
3. Enter your Crossbill server address and login details in the plugin.

## After the first sync

Open the book in the web app. It shows the book's chapters, its highlights
grouped by chapter, and its reading sessions.
