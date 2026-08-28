import { RHFTextField } from '@/components/inputs/RHFTextField.tsx';
import { Box, Button } from '@mui/material';
import { useForm, useWatch } from 'react-hook-form';

export interface FlashcardFormValues {
  question: string;
  answer: string;
}

const EMPTY_FORM: FlashcardFormValues = { question: '', answer: '' };

interface CreateFlashcardFormProps {
  editingFlashcardId: number | null;
  initialValues?: FlashcardFormValues;
  isDisabled: boolean;
  isProcessing: boolean;
  onSave: (values: FlashcardFormValues) => Promise<boolean>;
  onCancelEdit: () => void;
}

export const CreateFlashcardForm = ({
  editingFlashcardId,
  initialValues,
  isDisabled,
  isProcessing,
  onSave,
  onCancelEdit,
}: CreateFlashcardFormProps) => {
  const { control, handleSubmit, reset } = useForm<FlashcardFormValues>({
    defaultValues: initialValues ?? EMPTY_FORM,
  });

  const [question, answer] = useWatch({ control, name: ['question', 'answer'] });
  const canSave = question.trim() && answer.trim() && !isDisabled;

  const onSubmit = async (values: FlashcardFormValues) => {
    const saved = await onSave({
      question: values.question.trim(),
      answer: values.answer.trim(),
    });
    if (saved) reset(EMPTY_FORM);
  };

  const handleCancel = () => {
    reset(EMPTY_FORM);
    onCancelEdit();
  };

  return (
    <Box
      component="form"
      onSubmit={handleSubmit(onSubmit)}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        alignItems: 'flex-start',
      }}
    >
      <RHFTextField
        name="question"
        control={control}
        fullWidth
        size="small"
        placeholder="Question..."
        disabled={isDisabled}
      />
      <RHFTextField
        name="answer"
        control={control}
        fullWidth
        size="small"
        multiline
        minRows={2}
        maxRows={4}
        placeholder="Answer..."
        disabled={isDisabled}
      />
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, width: '100%' }}>
        {editingFlashcardId && (
          <Button
            variant="text"
            size="small"
            onClick={handleCancel}
            disabled={isDisabled}
            sx={{ flexShrink: 0, height: 'fit-content', mt: 0.5 }}
          >
            Cancel
          </Button>
        )}
        <Button
          type="submit"
          variant="text"
          size="small"
          disabled={!canSave}
          sx={{ flexShrink: 0, height: 'fit-content', mt: 0.5 }}
        >
          {isProcessing ? 'Saving...' : editingFlashcardId ? 'Save' : 'Add flashcard'}
        </Button>
      </Box>
    </Box>
  );
};
