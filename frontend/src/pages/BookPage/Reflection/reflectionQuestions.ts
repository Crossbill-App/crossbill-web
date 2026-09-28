import type { BookReflectionResponse } from '@/api/generated/model';

type ReflectionNoteIdField =
  | 'what_is_it_about_note_id'
  | 'what_does_it_say_note_id'
  | 'do_i_agree_note_id'
  | 'so_what_note_id';

/** Names the question's copy under `reflection.questions` in the locale files. */
type ReflectionQuestionKey = 'whatIsItAbout' | 'whatDoesItSay' | 'doIAgree' | 'soWhat';

export interface ReflectionQuestion {
  noteIdField: ReflectionNoteIdField;
  key: ReflectionQuestionKey;
}

export const REFLECTION_QUESTIONS: ReflectionQuestion[] = [
  {
    noteIdField: 'what_is_it_about_note_id',
    key: 'whatIsItAbout',
  },
  {
    noteIdField: 'what_does_it_say_note_id',
    key: 'whatDoesItSay',
  },
  {
    noteIdField: 'do_i_agree_note_id',
    key: 'doIAgree',
  },
  {
    noteIdField: 'so_what_note_id',
    key: 'soWhat',
  },
];

export const emptyReflection = (bookId: number): BookReflectionResponse => ({
  book_id: bookId,
  what_is_it_about_note_id: null,
  what_does_it_say_note_id: null,
  do_i_agree_note_id: null,
  so_what_note_id: null,
  note_ids: [],
});
