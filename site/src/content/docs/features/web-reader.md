---
title: Web reader
description: Read a book in the browser, jump from a highlight to its place in the book, and make highlights your e-reader also gets.
---

The **web reader** opens a book's EPUB file in the browser. It opens where you
left off, on whichever device you read last. If you also use the [KOReader plugin](../../getting-started/koreader-plugin/),
the highlights you make here reach your e-reader too.

## Adding a book

On the **Library** page, use the upload button in the bottom-right corner and
pick an EPUB file. Crossbill reads the book's title, chapters and cover from
the file and opens the new book.

- Only EPUB files are accepted, up to 50 MB.
- If the book is already in your library, the upload is rejected.
- A book synced from KOReader already has its EPUB; you do not need to upload
  it again.
- If you later sync the same EPUB from KOReader, the plugin finds the uploaded
  book and adds to it.

## Opening a book

Open a book in the reader from the book's read section. You can also jump to a
highlight or a chapter from its dialog.

## Reading

- **Turn pages** with the arrows at the edges of the page, the left and right
  arrow keys, or a swipe on a phone.
- **Contents** in the top-left corner lists the book's chapters. Pick one to go
  there.
- The footer shows how many pages are left in the chapter and how much of the
  book you have read.

Crossbill saves your place as you read. Reading in the browser creates reading
sessions, the same as on your e-reader. They count towards the book's progress
and your reading statistics.

Your e-reader keeps its own place. It does not jump to where you stopped in the
browser.

## Appearance

Change the reader's look in the appearance menu. The settings are saved only
in the browser where you set them.

## Highlighting

Your existing highlights are drawn on the page, in the colours your
[highlight styles](../highlights/#highlight-styles-and-labels) display in.

To make a new one, select some text. A bar appears under the selection:

- **Colour** picks the highlighter colour. The choices are KOReader's colours,
  named with your labels. You can use them without KOReader.
- **Highlight** saves the passage in that colour.
- **Extend** lets a highlight run past the current page. Turn to where the
  passage ends and tap its last word. An extended highlight must end in the
  chapter it started in.
- **Cancel** drops the selection.

## Limits

- The reader reads EPUB files only.
- Safari needs Crossbill served over HTTPS to show a book's images. Over plain
  HTTP, Safari shows the text with broken images; other browsers show both. See
  [Serving the web reader](../../getting-started/installation/#serving-the-web-reader).
