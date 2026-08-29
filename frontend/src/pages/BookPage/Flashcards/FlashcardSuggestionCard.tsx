import { IconButtonWithTooltip } from '@/components/buttons/IconButtonWithTooltip';
import { FlashcardCard } from '@/pages/BookPage/Flashcards/FlashcardCard.tsx';
import { AcceptIcon, RejectIcon } from '@/theme/Icons.tsx';

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
      borderColor="grey"
      renderActions={() => (
        <>
          <IconButtonWithTooltip
            label="Accept suggestion"
            onClick={handleAccept}
            icon={<AcceptIcon fontSize="small" />}
          />
          <IconButtonWithTooltip
            label="Reject suggestion"
            onClick={handleReject}
            icon={<RejectIcon fontSize="small" />}
          />
        </>
      )}
    />
  );
};
