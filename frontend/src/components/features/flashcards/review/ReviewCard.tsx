import type { FlashcardReviewRequestRating } from '@/api/generated/model';
import { Collapsable } from '@/components/animations/Collapsable.tsx';
import { Eyebrow } from '@/components/typography/Eyebrow.tsx';
import { HighlightQuote } from '@/pages/BookPage/common/HighlightContent.tsx';
import { EditIcon, NotesIcon, SuspendIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, Button, Divider, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { reviewInterval } from './reviewInterval.ts';
import { GRADES } from './useReviewKeys.ts';
import type { QueuedFlashcard } from './useReviewQueue.ts';

interface ReviewCardProps {
  card: QueuedFlashcard;
  revealed: boolean;
  onReveal: () => void;
  onGrade: (rating: FlashcardReviewRequestRating) => void;
  onEdit: () => void;
  onSuspend: () => void;
}

const CardSource = ({ card }: { card: QueuedFlashcard }) => {
  if (card.highlight_text) return <HighlightQuote text={card.highlight_text} />;
  if (!card.note_title) return null;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary' }}>
      <NotesIcon sx={{ fontSize: ICON_SIZE.ui }} />
      <Typography variant="body1">{card.note_title}</Typography>
    </Box>
  );
};

const GradeButtons = ({ card, onGrade }: Pick<ReviewCardProps, 'card' | 'onGrade'>) => {
  const { t } = useTranslation();

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' },
        gap: 1,
      }}
    >
      {GRADES.map(({ key, rating }) => {
        const interval = reviewInterval(Date.parse(card.previews[rating]) - card.fetchedAt);
        return (
          <Button
            key={rating}
            variant="outlined"
            aria-keyshortcuts={key}
            onClick={() => onGrade(rating)}
            sx={{ flexDirection: 'column', py: 1 }}
          >
            <span>{t(`review.grades.${rating}`)}</span>
            <Typography component="span" variant="body2" sx={{ color: 'text.secondary' }}>
              {t(`review.interval.${interval.unit}`, { count: interval.count })}
            </Typography>
          </Button>
        );
      })}
    </Box>
  );
};

export const ReviewCard = ({
  card,
  revealed,
  onReveal,
  onGrade,
  onEdit,
  onSuspend,
}: ReviewCardProps) => {
  const { t } = useTranslation();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
          {card.chapter_name
            ? t('review.card.context', { book: card.book_title, chapter: card.chapter_name })
            : card.book_title}
        </Typography>
        <Typography variant="h2" component="p">
          {card.question}
        </Typography>
      </Box>

      <Collapsable isExpanded={revealed}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Divider />
          <Box>
            <Eyebrow sx={{ mb: 0.5 }}>{t('flashcards.fields.answer')}</Eyebrow>
            <Typography variant="body1">{card.answer}</Typography>
          </Box>
          <CardSource card={card} />
          <GradeButtons card={card} onGrade={onGrade} />
        </Box>
      </Collapsable>
      <Collapsable isExpanded={!revealed}>
        <Button variant="contained" size="large" onClick={onReveal}>
          {t('review.card.showAnswer')}
        </Button>
      </Collapsable>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
        <Button startIcon={<EditIcon />} onClick={onEdit}>
          {t('common.actions.edit')}
        </Button>
        <Button startIcon={<SuspendIcon />} onClick={onSuspend}>
          {t('review.card.suspend')}
        </Button>
      </Box>
    </Box>
  );
};
