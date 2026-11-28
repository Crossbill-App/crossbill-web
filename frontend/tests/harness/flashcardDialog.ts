import type { renderApp } from '@tests/harness/renderApp';
import { expect } from 'vitest';
import { userEvent } from 'vitest/browser';

type Screen = Awaited<ReturnType<typeof renderApp>>;

interface FlashcardText {
  question?: string;
  answer?: string;
}

/** Opens the Flashcards tab of the entity dialog on screen. */
export const openFlashcardsTab = async (screen: Screen) => {
  await userEvent.click(screen.getByRole('tab', { name: /^Flashcards/ }));
  return screen.getByRole('tabpanel');
};

/** Fills the open flashcard dialog, saves, and waits for it to close. */
export const saveFlashcardDialog = async (
  screen: Screen,
  title: 'New flashcard' | 'Edit flashcard',
  { question, answer }: FlashcardText
) => {
  const dialog = screen.getByRole('dialog', { name: title });
  if (question !== undefined) {
    await userEvent.fill(dialog.getByRole('textbox', { name: 'Question' }), question);
  }
  if (answer !== undefined) {
    await userEvent.fill(dialog.getByRole('textbox', { name: 'Answer' }), answer);
  }
  await userEvent.click(dialog.getByRole('button', { name: 'Save' }));
  await expect.element(dialog).not.toBeInTheDocument();
};

/**
 * Rewrites the question of the only card in the entity dialog's Flashcards tab
 * and proves the tab lists the new question in place of the old.
 */
export const expectQuestionEditedInTab = async (screen: Screen, from: string, to: string) => {
  const panel = await openFlashcardsTab(screen);
  await userEvent.click(panel.getByRole('button', { name: 'Edit flashcard' }));
  await saveFlashcardDialog(screen, 'Edit flashcard', { question: to });

  await expect.element(panel.getByRole('button', { name: to })).toBeVisible();
  expect(panel.getByRole('button', { name: from }).elements()).toHaveLength(0);
};
