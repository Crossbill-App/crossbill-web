import { useCallback, useEffect, useState } from 'react';

import { CommonDialog } from '@/components/dialogs/CommonDialog.tsx';
import { CommonDialogTitle } from '@/components/dialogs/CommonDialogTitle.tsx';

import { ChatInput } from './chat/ChatInput.tsx';
import { type ChatMessage, ChatMessageList } from './chat/ChatMessageList.tsx';
import { SessionError } from './chat/SessionError.tsx';
import type { ChatVariant } from './chatVariants.ts';

interface ChatDialogProps {
  open: boolean;
  onClose: () => void;
  chapterId: number;
  chapterName: string;
  variant: ChatVariant;
  onSaveNote?: (content: string) => void;
}

const ERROR_MESSAGE = 'Something went wrong. The AI service may be temporarily unavailable.';

/** Wrapper that remounts inner content each time the dialog opens, giving fresh state. */
export const ChatDialog = ({
  open,
  onClose,
  chapterId,
  chapterName,
  variant,
  onSaveNote,
}: ChatDialogProps) => {
  const title = <CommonDialogTitle>{variant.title(chapterName)}</CommonDialogTitle>;

  return (
    <CommonDialog open={open} onClose={onClose} maxWidth="md" title={title}>
      {open && <ChatContent chapterId={chapterId} variant={variant} onSaveNote={onSaveNote} />}
    </CommonDialog>
  );
};

interface ChatContentProps {
  chapterId: number;
  variant: ChatVariant;
  onSaveNote?: (content: string) => void;
}

const ChatContent = ({ chapterId, variant, onSaveNote }: ChatContentProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { mutate: createSession, isPending: isCreating } = variant.useCreateSession({
    mutation: {
      onSuccess: (data) => {
        setError(null);
        setSessionId(data.session_id);
        setMessages([{ role: 'assistant', content: data.message }]);
      },
      onError: () => {
        setError(ERROR_MESSAGE);
      },
    },
  });

  const { mutate: sendMessage, isPending: isSending } = variant.useSendMessage({
    mutation: {
      onSuccess: (data) => {
        setError(null);
        setMessages((prev) => [...prev, { role: 'assistant', content: data.message }]);
      },
      onError: () => {
        // Remove the optimistically-added user message and restore it to input
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last.role === 'user') {
            setInput(last.content);
            return prev.slice(0, -1);
          }
          return prev;
        });
        setError(ERROR_MESSAGE);
      },
    },
  });

  // Start session on mount
  useEffect(() => {
    createSession({ chapterId });
  }, [createSession, chapterId]);

  const handleSend = useCallback(() => {
    if (!input.trim() || !sessionId || isSending) return;

    setError(null);
    const userMessage = input.trim();
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setInput('');

    sendMessage({ sessionId, data: { message: userMessage } });
  }, [input, sessionId, isSending, sendMessage]);

  const handleRetryCreate = useCallback(() => {
    setError(null);
    createSession({ chapterId });
  }, [createSession, chapterId]);

  const hasSessionError = !!(error && !sessionId);

  return (
    <>
      <SessionError
        error={error}
        hasSession={sessionId !== null}
        isCreating={isCreating}
        onRetry={handleRetryCreate}
      />
      <ChatMessageList
        messages={messages}
        isLoading={isSending}
        error={error}
        onSaveNote={onSaveNote}
      />
      <ChatInput
        value={input}
        placeholder={variant.inputPlaceholder}
        onChange={setInput}
        onSend={handleSend}
        disabled={isSending || isCreating || hasSessionError}
        sendDisabled={!input.trim() || isSending || isCreating}
      />
    </>
  );
};
