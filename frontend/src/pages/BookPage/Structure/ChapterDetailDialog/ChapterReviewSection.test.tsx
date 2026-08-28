import { aBookDetails, aChapter } from '@tests/fixtures/book';
import { aChapterDigest, aDigestQuestion } from '@tests/fixtures/digest';
import { renderApp } from '@tests/harness/renderApp';
import { settingsWithAi } from '@tests/msw/auth';
import { bookApi } from '@tests/msw/bookApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const ANSWER_PLACEHOLDER = 'Write your answer...';
const CHAPTER = aChapter({ id: 10, name: 'Attention and memory' });

/** The chapter dialog with two digest questions, opened straight from the URL. */
const openChapterDialog = async () => {
  const { handlers, state } = bookApi({
    book: aBookDetails({ chapters: [CHAPTER] }),
    digests: [
      aChapterDigest({
        chapter_id: CHAPTER.id,
        questions: [
          aDigestQuestion({ question: 'What makes attention a filter?' }),
          aDigestQuestion({ question: 'Where does the spotlight metaphor fail?' }),
        ],
      }),
    ],
  });
  worker.use(settingsWithAi(true), ...handlers);

  const screen = await renderApp({ path: '/book/1/structure?chapterId=10' });
  const dialog = screen.getByRole('dialog');
  await expect.element(dialog.getByText('What makes attention a filter?')).toBeVisible();

  return { screen, dialog, state };
};

test('an answer is saved when the reader leaves the field', async () => {
  const { dialog, state } = await openChapterDialog();

  await userEvent.fill(
    dialog.getByPlaceholder(ANSWER_PLACEHOLDER).first(),
    'It gates what is kept.'
  );
  await userEvent.tab();

  await expect.poll(() => state.digests[0].questions[0].user_answer).toBe('It gates what is kept.');
  await expect
    .element(dialog.getByPlaceholder(ANSWER_PLACEHOLDER).first())
    .toHaveValue('It gates what is kept.');
});

test('answering the second question keeps the first answer', async () => {
  const { dialog, state } = await openChapterDialog();
  const fields = dialog.getByPlaceholder(ANSWER_PLACEHOLDER);

  await userEvent.fill(fields.first(), 'It gates what is kept.');
  await userEvent.tab();
  await expect.poll(() => state.digests[0].questions[0].user_answer).toBe('It gates what is kept.');

  await userEvent.fill(fields.last(), 'A spotlight cannot suppress.');
  await userEvent.tab();

  await expect
    .poll(() => state.digests[0].questions[1].user_answer)
    .toBe('A spotlight cannot suppress.');
  expect(state.digests[0].questions[0].user_answer).toBe('It gates what is kept.');
});

test('Escape reverts an answer instead of closing the chapter dialog', async () => {
  const { dialog, state } = await openChapterDialog();

  await userEvent.fill(dialog.getByPlaceholder(ANSWER_PLACEHOLDER).first(), 'Half a thought');
  await userEvent.keyboard('{Escape}');

  await expect.element(dialog.getByPlaceholder(ANSWER_PLACEHOLDER).first()).toHaveValue('');
  await expect.element(dialog.getByText('What makes attention a filter?')).toBeVisible();
  expect(state.digests[0].questions[0].user_answer).toBe('');
});

test('a failed save reports the error and keeps the answer on screen', async () => {
  const { screen, dialog } = await openChapterDialog();
  worker.use(
    http.put(
      '/api/v1/chapters/:chapterId/digest/answers',
      () => new HttpResponse(null, { status: 500 })
    )
  );

  await userEvent.fill(dialog.getByPlaceholder(ANSWER_PLACEHOLDER).first(), 'Worth keeping.');
  await userEvent.tab();

  await expect.element(screen.getByText('Failed to save answer. Please try again.')).toBeVisible();
  await expect
    .element(dialog.getByPlaceholder(ANSWER_PLACEHOLDER).first())
    .toHaveValue('Worth keeping.');
});
