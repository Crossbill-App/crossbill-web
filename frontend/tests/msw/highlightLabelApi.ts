import type { BookDetails, HighlightLabel, HighlightLabelInBook } from '@/api/generated/model';
import { http, HttpResponse } from 'msw';
import { aBookDetails, aChapter, aHighlight, KOREADER_HUE } from '../fixtures/book';
import { bookApi } from './bookApi';
import { worker } from './worker';

/** The style a colour the caller did not list is filed under. */
const UNLISTED_STYLE_ID = 999;

interface Recorded {
  url: string;
  body: unknown;
}

export interface HighlightLabelApi {
  /** Every request that moved one highlight to another colour, in order. */
  recolours: Recorded[];
  /** Every request that renamed or recoloured a label, in order. */
  relabels: Recorded[];
}

/** A book of one highlight, for a test that cares only about the labels beside it. */
const aBookOfOneHighlight = (): BookDetails =>
  aBookDetails({
    chapters: [
      aChapter({ id: 10, highlights: [aHighlight({ id: 300, text: 'The lantern went out' })] }),
    ],
  });

/** The book with one highlight now wearing another label, as a recolour leaves it. */
const withLabel = (book: BookDetails, highlightId: number, label: HighlightLabel): BookDetails => ({
  ...book,
  chapters: book.chapters.map((chapter) => ({
    ...chapter,
    highlights: chapter.highlights.map((highlight) =>
      highlight.id === highlightId ? { ...highlight, label } : highlight
    ),
  })),
});

/**
 * Serves a book and its highlighters, and records what each edit asks for.
 *
 * The two edits are told apart by which endpoint they reach, which is the whole
 * point of the split: `.../highlights/:id/color` moves one highlight, where
 * `/highlight-labels/:id` writes the label every highlight of that colour
 * shares. A test asserting "only this highlight moved" reads it off `recolours`
 * being the only list with anything in it.
 *
 * A recolour really does move the highlight here, so the book served afterwards
 * reports the label of the colour it landed in. That is what makes the swap
 * from an unnamed colour's dot to a named one's chip observable at all, and a
 * popover anchored to the old element is what put it in the screen's corner.
 *
 * Installs the handlers itself, ahead of `bookApi`'s defaults, because the
 * first matching handler wins and `bookApi` serves an empty label list.
 */
export function highlightLabelApi(
  labels: HighlightLabelInBook[],
  book: BookDetails = aBookOfOneHighlight()
): HighlightLabelApi {
  const recolours: Recorded[] = [];
  const relabels: Recorded[] = [];
  let served = book;

  const record = async (into: Recorded[], request: Request) => {
    const body = await request.json();
    into.push({ url: new URL(request.url).pathname, body });
    return body as Record<string, string>;
  };

  const handlers = [
    http.get('/api/v1/books/:bookId', () => HttpResponse.json(served)),
    http.get('/api/v1/books/:bookId/highlight-labels', () => HttpResponse.json({ items: labels })),
    http.patch(
      '/api/v1/books/:bookId/highlights/:highlightId/color',
      async ({ params, request }) => {
        const body = await record(recolours, request);
        const landed = labels.find((label) => label.device_color === body.device_color);
        const moved: HighlightLabel = {
          // Never zero: a falsy style id reads as "this highlight has no label"
          // and would take the editor off the screen rather than move it.
          highlight_style_id: landed?.id ?? UNLISTED_STYLE_ID,
          text: landed?.label ?? null,
          ui_color: landed?.ui_color ?? KOREADER_HUE.red,
        };
        served = withLabel(served, Number(params.highlightId), moved);
        return HttpResponse.json(moved);
      }
    ),
    http.patch('/api/v1/highlight-labels/:styleId', async ({ request }) => {
      await record(relabels, request);
      return HttpResponse.json(labels[0]);
    }),
  ];

  worker.use(...handlers, ...bookApi({ book }).handlers);

  return { recolours, relabels };
}
