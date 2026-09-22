import { aBookDetails, aChapter } from '@tests/fixtures/book';
import { aNote } from '@tests/fixtures/notes';
import { renderApp } from '@tests/harness/renderApp';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const PLACEHOLDER = 'What was this chapter about?';
const CHAPTER = aChapter({ id: 10, name: 'Attention and memory' });

/**
 * The gist the tests below edit. Named rather than repeated as a literal so
 * each assertion is bound to the fixture it is about, and so the prose is
 * visibly the test's own rather than the app's copy.
 */
const THE_SAVED_GIST = 'A first pass.';
const THE_REWRITTEN_GIST = 'A second, better pass.';

const aGist = (body: string) =>
  aNote({ id: 100, title: CHAPTER.name, body, kind: 'gist', chapter_ids: [CHAPTER.id] });

/** The chapter dialog, opened straight from the URL and settled. */
const openChapterDialog = async (notes = [] as ReturnType<typeof aNote>[]) => {
  const { handlers, state } = bookApi({ book: aBookDetails({ chapters: [CHAPTER] }), notes });
  worker.use(...handlers);

  const screen = await renderApp({ path: '/book/1/structure?chapterId=10' });
  const dialog = screen.getByRole('dialog');
  await expect.element(dialog.getByText('Gist')).toBeVisible();

  return { screen, dialog, state };
};

test('a gist is written from the chapter dialog without a second dialog opening', async () => {
  const { screen, dialog, state } = await openChapterDialog();

  await userEvent.fill(
    dialog.getByPlaceholder(PLACEHOLDER),
    'Attention is a filter, not a spotlight.'
  );
  await userEvent.tab();

  await expect
    .element(dialog.getByRole('button', { name: 'Attention is a filter, not a spotlight.' }))
    .toBeVisible();
  expect(screen.getByRole('heading', { name: 'New note' }).elements()).toHaveLength(0);

  await expect.poll(() => state.notes.length).toBe(1);
  expect(state.notes[0]).toMatchObject({
    kind: 'gist',
    title: 'Attention and memory',
    body: 'Attention is a filter, not a spotlight.',
    chapter_ids: [10],
  });
});

test('a new gist cannot be edited into a duplicate while its create is pending', async () => {
  const { dialog, state } = await openChapterDialog();
  let finishCreate: (() => void) | undefined;
  const createCanFinish = new Promise<void>((resolve) => {
    finishCreate = resolve;
  });
  worker.use(
    http.post('/api/v1/notes', async () => {
      await createCanFinish;
      state.notes.push(aGist('Attention is selective.'));
      return HttpResponse.json({ success: true, message: 'Note created', note: state.notes[0] });
    })
  );

  const field = dialog.getByPlaceholder(PLACEHOLDER);
  await userEvent.fill(field, 'Attention is selective.');
  await userEvent.tab();

  await expect.element(field).toBeDisabled();
  finishCreate?.();

  // The saved gist renders as a button; `getByText` would match the field's own
  // textarea and pass before the create has even been answered.
  await expect
    .element(dialog.getByRole('button', { name: 'Attention is selective.' }))
    .toBeVisible();
  expect(state.notes).toHaveLength(1);
});

test('an existing gist is edited in place, keeping the links it already had', async () => {
  const { dialog, state } = await openChapterDialog([
    { ...aGist(THE_SAVED_GIST), tag_ids: [7], chapter_ids: [10, 11] },
  ]);

  await userEvent.click(dialog.getByText(THE_SAVED_GIST));
  await userEvent.fill(dialog.getByPlaceholder(PLACEHOLDER), THE_REWRITTEN_GIST);
  await userEvent.keyboard('{Enter}');

  await expect.element(dialog.getByText(THE_REWRITTEN_GIST)).toBeVisible();
  await expect.poll(() => state.notes[0].body).toBe(THE_REWRITTEN_GIST);
  expect(state.notes[0]).toMatchObject({
    body: THE_REWRITTEN_GIST,
    tag_ids: [7],
    chapter_ids: [10, 11],
  });
});

test('Escape reverts the edit and leaves the saved gist alone', async () => {
  const { dialog, state } = await openChapterDialog([aGist(THE_SAVED_GIST)]);

  await userEvent.click(dialog.getByText(THE_SAVED_GIST));
  await userEvent.fill(dialog.getByPlaceholder(PLACEHOLDER), 'Half a thought');
  await userEvent.keyboard('{Escape}');

  await expect.element(dialog.getByText(THE_SAVED_GIST)).toBeVisible();
  expect(state.notes[0].body).toBe(THE_SAVED_GIST);
});

test('clearing the text deletes the gist', async () => {
  const { screen, dialog, state } = await openChapterDialog([aGist(THE_SAVED_GIST)]);

  await userEvent.click(dialog.getByText(THE_SAVED_GIST));
  await userEvent.fill(dialog.getByPlaceholder(PLACEHOLDER), '');
  await userEvent.tab();

  await expect.element(screen.getByRole('alert')).toBeVisible();
  await expect.element(dialog.getByPlaceholder(PLACEHOLDER)).toBeVisible();
  expect(state.notes).toHaveLength(0);
});

test('a failed save keeps the text on screen and says it did not save', async () => {
  const { dialog } = await openChapterDialog();
  worker.use(http.post('/api/v1/notes', () => new HttpResponse(null, { status: 500 })));

  await userEvent.fill(dialog.getByPlaceholder(PLACEHOLDER), 'Worth keeping.');
  await userEvent.tab();

  // The failure is on the field the text is still in, not in a snackbar that
  // fades: the editor stays invalid until the save is retried.
  const editor = dialog.getByPlaceholder(PLACEHOLDER);
  await expect.element(editor).toHaveAttribute('aria-invalid', 'true');
  await expect.element(editor).toHaveValue('Worth keeping.');
});
