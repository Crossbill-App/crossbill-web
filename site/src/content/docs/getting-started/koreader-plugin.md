---
title: KOReader plugin
description: What the KOReader plugin syncs between your e-reader and Crossbill, and where to find its install instructions.
---

Crossbill gets its content from your e-reader. The
[KOReader plugin](https://github.com/Crossbill-App/koreader-plugin) runs
inside KOReader on the device and talks to your Crossbill server.

## What it syncs


- **Highlights** — the passages you marked while reading, with where they sit in
  the book, any note you typed about one on the device, and which device it came
  from. 
- **Highlight styles** — the highlighter appearance you used: a colour, a
  drawing style, or both. Crossbill keeps them so you can give each one a
  [label](../../features/tags-and-organization/) later.
- **Reading sessions** — the stretches of reading KOReader recorded: when each
  one started and ended, and how far through the book it ran.
- **Chapter digests** — the plugin can pull generated digests back down so you
  can read a chapter's summary and key points on the device itself.

If you read the same book on more than one e-reader, edits to a highlight's
note or its colour are merged by when they were made. The most recent change
wins, whichever device made it.

## Deleting a highlight

Deleting a highlight on the e-reader takes it off your devices, not out of
Crossbill. The next sync reports it, the server withholds it from every device's
pull, and the web copy stays whole — the notes, flashcards, tags and bookmarks
hanging off it are untouched. In the web app it carries a **Deleted on the
e-reader** chip. To be rid of it everywhere, delete it in Crossbill instead:
that deletion reaches every device.

When a sync would withdraw every highlight the device ever pulled for a book,
the plugin asks first. A KOReader sidecar file that went missing looks exactly
like a book the reader emptied on purpose, so choose **Keep** and the server's
copy stays put while the rest of the sync runs. An automatic background sync has
nobody to ask, so it skips the removal and leaves it for a manual sync.

## Highlighting a passage again

Marking a passage you had deleted brings the stored highlight back rather than
adding a second one beside it. The plugin knows the highlight never came down
from the server, so it tells Crossbill this was deliberate, and the row returns
with its tags — and, if it was only withheld from your devices, with its
flashcards and bookmarks too. A highlight you deleted in Crossbill comes back
without them: its flashcards and bookmarks went with that deletion and are not
recoverable.

This works from the book's second sync onwards. On the first sync of a book on a
new device, the plugin cannot yet tell an old sidecar from a fresh highlight, so
it revives nothing — sync once, and the sync after that behaves normally.

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
