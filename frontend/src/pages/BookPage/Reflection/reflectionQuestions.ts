import type { BookReflectionResponse } from '@/api/generated/model';

type ReflectionNoteIdField =
  | 'what_is_it_about_note_id'
  | 'what_does_it_say_note_id'
  | 'do_i_agree_note_id'
  | 'so_what_note_id';

export interface ReflectionQuestion {
  noteIdField: ReflectionNoteIdField;
  title: string;
  guide: string;
}

export const REFLECTION_QUESTIONS: ReflectionQuestion[] = [
  {
    noteIdField: 'what_is_it_about_note_id',
    title: 'What is the book about?',
    guide:
      'State what the whole book is about in a single sentence. Then outline its major parts, and name the problems the author set out to solve.',
  },
  {
    noteIdField: 'what_does_it_say_note_id',
    title: 'What does it say in detail?',
    guide:
      "The author's key terms, most important propositions, and the arguments behind them. Link your term and concept notes below — that's how you come to terms with the author.",
  },
  {
    noteIdField: 'do_i_agree_note_id',
    title: 'Do I agree?',
    guide:
      'Judge the book. Is the author uninformed (missing something important), misinformed (working from false premises), or illogical (reasoning doesn’t hold)? If none apply, you are obligated to agree — say so.',
  },
  {
    noteIdField: 'so_what_note_id',
    title: 'So what?',
    guide:
      "If the book is true, what follows? What will you do or think differently? How does it connect with other books you've read?",
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
