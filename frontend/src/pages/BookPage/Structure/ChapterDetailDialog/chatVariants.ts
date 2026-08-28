import {
  useCreateChatSession,
  useCreateQuizSession,
  useSendChatMessage,
  useSendQuizMessage,
} from '@/api/generated/chat/chat';

/**
 * A chat variant selects which backend endpoints back the {@link ChatDialog}. Quiz is
 * just a sub-type of chat, so both share the same request/response shapes and UI. The
 * `use*` hooks are structurally identical across variants (see generated chat API).
 */
export interface ChatVariant {
  title: (chapterName: string) => string;
  /** What the input asks for. The two variants ask for different things. */
  inputPlaceholder: string;
  useCreateSession: typeof useCreateChatSession;
  useSendMessage: typeof useSendChatMessage;
}

export const CHAT_VARIANT: ChatVariant = {
  title: (chapterName) => `Chat: ${chapterName}`,
  inputPlaceholder: 'Ask about this chapter...',
  useCreateSession: useCreateChatSession,
  useSendMessage: useSendChatMessage,
};

export const QUIZ_VARIANT: ChatVariant = {
  title: (chapterName) => `Quiz: ${chapterName}`,
  inputPlaceholder: 'Type your answer...',
  useCreateSession: useCreateQuizSession,
  useSendMessage: useSendQuizMessage,
};
