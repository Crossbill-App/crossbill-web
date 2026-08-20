# Crossbill

A self-hosted reading companion. Crossbill collects what a reader marked on
their e-reader and gives them the tools to work it into understanding — in the
spirit of Mortimer J. Adler's _How to Read a Book_, whose levels of reading and
four analytical questions this domain borrows directly.

## Language

### Library

**Book**:
A book in a user's library. Metadata plus, optionally, the EPUB file itself.
_Avoid_: title, publication, document, work

**Chapter**:
An entry in a book's table of contents. Chapters nest, so a chapter may be a
part, a section, or a leaf.
_Avoid_: section, TOC entry, heading

**Reading Stage**:
The engagement stage a user has set for a book by hand — _to read_, _skimming_,
_reading_, _finished_, _reflected_. It is declared, never inferred from
activity.
_Avoid_: status, state, progress

### Reading

**Highlight**:
A passage of text the user marked on their e-reader, imported into Crossbill. A
highlight carries the passage and where it sits in the book, plus any note the
user typed on the e-reader and the device it came from. The words they write
about it in Crossbill live in a Note.
_Avoid_: annotation, clipping, excerpt, quote, passage

**Highlight Style**:
A highlighter appearance on the e-reader — a colour, a drawing style, or the
combination of both — that the user can name and recolour for display.
_Avoid_: colour, marker, pen

**Label**:
The meaning a user assigned to a Highlight Style: what they meant when they
reached for the yellow highlighter. A highlight inherits at most one label,
from the device. Contrast Tag, which the user applies in Crossbill and can
apply many of. A label may be set per book or globally, and resolves down a
fallback chain from the most specific match to the least.
_Avoid_: category, tag, name

**Bookmark**:
A highlight saved into a book's index so the user can jump back to it. A book
has many. Bookmarks say nothing about reading progress.
_Avoid_: pin, favourite, star, progress marker

**Reading Session**:
A continuous stretch of reading that the e-reader recorded — when it started
and ended, and how far through the book it ran.
_Avoid_: session (bare — see AI Chat Session), sitting

**Skimming**:
Adler's second level of reading — systematic skimming and superficial reading —
done to find out what a book or chapter contains before reading it properly.
One of the reading stages, and the activity a Chapter Digest is meant to
support.
_Avoid_: scanning, browsing, previewing

**Chapter Digest**:
An AI-generated condensation of one chapter: a summary, its keypoints, and
comprehension questions the user can answer. Read before the chapter to support
Skimming, or after it as review — the artifact is the same either way.
_Avoid_: prereading content, chapter summary, chapter overview

### Organizing

**Tag**:
A category the user created and applied to highlights and notes. Tags are
scoped to a single book — the same word used in two books is two tags. Contrast
Label, which comes from the e-reader.
_Avoid_: label, keyword, category, topic

**Tag Group**:
A named cluster of a book's tags, used to organize them.
_Avoid_: category, folder, collection

**Note**:
A piece of writing the user authored — about a term, a character, a concept,
the gist of something, or as a reflection. A note always belongs to at least
one book, and may link to chapters, highlights and tags.
_Avoid_: annotation, comment, remark, entry

### Reflection and learning

**Book Reflection**:
A user's answers to Adler's four analytical-reading questions about one book:
what is it about, what does it say, do I agree, and so what. One per book. It
is a container — each answer is itself a Note — and it also gathers the term
and concept notes the user wrote while coming to terms with the author.
_Avoid_: review, summary, analysis

**Reflection Note**:
A Note serving as one of the four answers within a Book Reflection. The
reflection is the whole; a reflection note is a part.
_Avoid_: reflection (bare — that names the whole)

**Flashcard**:
A question-and-answer study card the user made from a highlight, a chapter, or
a note, for review by spaced repetition.
_Avoid_: card, quiz item, cloze

**AI Chat Session**:
A conversation between the user and the AI about a chapter — a quiz, or an open
discussion.
_Avoid_: session (bare — see Reading Session), chat, thread

### People and devices

**User**:
A person with an account on this Crossbill instance. Crossbill is multi-user and
every book, highlight and note belongs to exactly one of them.
_Avoid_: account, owner, member

**E-reader**:
The user's reading device, running the KOReader plugin. It is the origin of
highlights, highlight styles and reading sessions, and it can pull chapter
digests back down for reading on the device, as well as the server's copy of a
book's highlights. When two e-readers edit the same highlight, the newer edit
wins.
_Avoid_: client, device, KOReader (when speaking of the role rather than the
software)
