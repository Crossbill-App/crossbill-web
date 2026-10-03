---
title: Chapter digests
description: AI summaries, key points and comprehension questions for a chapter, for skimming before reading or for review after.
---

A **chapter digest** is an AI-generated summary of one chapter, with key points
and comprehension questions. Read it before the chapter to **skim**, that is,
to find out what the chapter contains. Or read it after the chapter as review.

Crossbill generates digests from the book's EPUB file, so the book needs its
file uploaded.

## Generating a digest

Open a book's **Structure** tab. It shows the chapters as a tree. Each chapter
shows its highlight and flashcard counts, whether you have read it, and its gist
if you wrote one.

- To generate a digest, open a chapter and choose **Generate summary**. The
  summary and key points appear in the chapter with the date they were made.
- To replace a digest, choose **Regenerate**.
- To generate digests for the whole book, choose **Generate summaries for all
  chapters**. The tab shows the progress, and you can cancel the run.

Whole-book generation runs in the
[background worker](../../getting-started/optional-components/#background-worker),
so you can close the page while it runs.

The Structure tab also has a [semantic search](../semantic-search/) field. It
shows the chapters whose digest matches your search.

## Using a digest

- The **key points** are a short bullet list.
- Each **comprehension question** has an answer box. Your answer saves when you
  click outside the box.
- You can **quiz yourself** on the chapter or **chat about it** with the AI.
- You can make a [note](../notes/) or a [flashcard](../flashcards/) from the
  same chapter view.

The [KOReader plugin](../../getting-started/koreader-plugin/) can download
digests to your e-reader, so you can read them next to the chapter.

## AI providers

Crossbill supports Ollama, OpenAI, Anthropic and Gemini. Set the provider with
`AI_PROVIDER` and its API key. The AI features appear in the app only after you
set a provider.
