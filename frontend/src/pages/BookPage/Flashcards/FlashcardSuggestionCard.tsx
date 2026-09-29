import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { FlashcardCard } from '@/pages/BookPage/Flashcards/FlashcardCard.tsx';
import { AcceptIcon, RejectIcon } from '@/theme/Icons.tsx';
import { useTranslation } from 'react-i18next';

export interface FlashcardSuggestionCardProps {
  question: string;
  answer: string;
  onAccept: () => void;
  onReject: () => void;
}

export const FlashcardSuggestionCard = ({
  question,
  answer,
  onAccept,
  onReject,
}: FlashcardSuggestionCardProps) => {
  const { t } = useTranslation();
  const handleAccept = (e: React.MouseEvent) => {
    e.stopPropagation();
    onAccept();
  };

  const handleReject = (e: React.MouseEvent) => {
    e.stopPropagation();
    onReject();
  };

  return (
    <FlashcardCard
      question={question}
      answer={answer}
      renderActions={() => (
        <>
          <IconButtonWithTooltip
            label={t('flashcards.aiSuggestions.accept')}
            onClick={handleAccept}
            icon={<AcceptIcon fontSize="small" />}
          />
          <IconButtonWithTooltip
            label={t('flashcards.aiSuggestions.reject')}
            onClick={handleReject}
            icon={<RejectIcon fontSize="small" />}
          />
        </>
      )}
    />
  );
};
