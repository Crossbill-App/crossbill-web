---
title: Chapter digests
description: AI summaries, key points and comprehension questions for a chapter — for skimming before, or review after.
---

A **chapter digest** is an AI-generated condensation of one chapter: a summary,
its key points, and comprehension questions you can answer. Read it before the
chapter to support **skimming** — finding out what the chapter contains before
reading it properly — or after the chapter as review. The artifact is the same
either way.

Digests are generated from the book's EPUB file, so a book needs its file
uploaded for this to work.

## Generating one

Open a book's **Structure** tab. It shows the book's chapters as a tree, with
each chapter's highlight and flashcard counts, whether you have read past it,
and its gist if you wrote one.

- Open a chapter and choose **Generate summary**. The summary and its key points
  appear in the chapter, with the date they were generated.
- **Regenerate** replaces a digest you already have.
- **Generate summaries for all chapters** runs the whole book at once. Progress
  is shown as it goes, and you can cancel a run partway.

Batch generation is what the optional
[background worker](../../getting-started/optional-components/) is for — it
processes the jobs outside the request, so you can close the page.

## Working with a digest

- The **key points** are a bullet list you can skim in a few seconds.
- The **comprehension questions** each have an answer box. Write your answer as
  you read; it saves when you click away.
- You can also **quiz yourself** on the chapter or **chat about it** with the AI
  in a conversation.
- Anything worth keeping can become a [note](../notes/) or a
  [flashcard](../flashcards/) from the same chapter view.

The [KOReader plugin](../../getting-started/koreader-plugin/) can pull digests
back down to the e-reader, so you can read them next to the chapter itself.

## AI providers

Ollama, OpenAI, Anthropic and Gemini are supported. Configure a provider with
`AI_PROVIDER` and its API key; the AI features only appear in the interface once
one is set up.
