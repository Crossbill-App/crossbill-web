---
title: KOReader
description: The optional plugin that syncs highlights, highlight styles and reading sessions from your e-reader.
---

[KOReader](https://koreader.rocks/) is the e-reader software Crossbill syncs
with. The Crossbill plugin runs inside it, on the device.

## What it does

- Sync your **highlights** with Crossbill and between multiple devices
- Uploads the **highlight styles** you used, so you can name and recolour them
  as [labels](../../features/tags-and-organization/) in Crossbill.
- Uploads your **reading sessions** — when each stretch of reading started and
  ended, and how far through the book it ran.
- Pulls **chapter digests** back down to the device, so a chapter's summary and
  key points are available while you read.

Across two e-readers, edits to a highlight's note or colour are merged by
newest edit: the most recent change wins, whichever device made it. Deleting a
highlight on the e-reader withdraws it from every device but leaves the web copy
whole, marked **Deleted on the e-reader**; delete it in Crossbill instead and it
goes everywhere. See [KOReader
plugin](../../getting-started/koreader-plugin/#deleting-a-highlight) for what
the plugin asks before withdrawing a whole book's worth.

The plugin is optional. Without an e-reader, upload EPUBs from the **Library**
page and read and highlight them in the [web reader](../../features/web-reader/).
A book you uploaded is the same book the plugin finds when it syncs that EPUB
later.

## Getting it

Installation instructions live with the plugin, so they stay current with
KOReader itself:

- [Crossbill-App/koreader-plugin](https://github.com/Crossbill-App/koreader-plugin)

See also [KOReader plugin](../../getting-started/koreader-plugin/) for what to
expect after your first sync.
