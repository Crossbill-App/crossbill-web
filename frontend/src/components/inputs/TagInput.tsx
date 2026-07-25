import { TagInBook } from '@/api/generated/model';
import { Autocomplete, Box, Chip, TextField, Typography } from '@mui/material';
import { useRef } from 'react';

/**
 * Base props shared by both form and immediate modes of TagInput
 */
export interface BaseTagInputProps {
  /** Label text for the input field */
  label?: string;
  /** Placeholder text shown when input is empty */
  placeholder?: string;
  /** Helper text shown below the input */
  helperText?: string;
  /** Whether the input is disabled */
  disabled?: boolean;
  /** Whether to blur the input after selecting an option (default: false for better UX) */
  blurOnSelect?: boolean;
  /** Whether to prevent parent navigation (useful in modals, default: false) */
  preventParentNavigation?: boolean;
  /** ARIA description for chips (default: 'Selected tag, click to remove') */
  chipAriaDescription?: string;
}

interface TagAutocompleteProps<T> {
  value: T[];
  onChange: (newValue: T[]) => void | Promise<void>;
  onBlur?: () => void;
  options: T[];
  disabled: boolean;
  blurOnSelect: boolean;
  placeholder: string;
  helperText: string;
  preventParentNavigation: boolean;
  chipAriaDescription: string;
  getOptionLabel: (option: T | string) => string;
  isOptionEqualToValue?: (option: T, value: T) => boolean;
  label?: string;
  showLabelAsTypography?: boolean;
}

export const TagAutocomplete = <T,>({
  value,
  onChange,
  onBlur,
  options,
  disabled,
  blurOnSelect,
  placeholder,
  helperText,
  preventParentNavigation,
  chipAriaDescription,
  getOptionLabel,
  isOptionEqualToValue,
  label,
  showLabelAsTypography = false,
}: TagAutocompleteProps<T>) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const handleChange = (newValue: T[]) => {
    const result = onChange(newValue);

    // Retain focus after change completes (sync or async)
    if (result instanceof Promise) {
      void result.then(() => {
        setTimeout(() => {
          inputRef.current?.focus();
        }, 0);
      });
    } else {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
    }
  };

  return (
    <Box data-prevent-navigation={preventParentNavigation || undefined}>
      {showLabelAsTypography && label && (
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          {label}
        </Typography>
      )}
      <Autocomplete
        multiple
        freeSolo
        options={options}
        value={value}
        onChange={(_, newValue) => handleChange(newValue as T[])}
        onBlur={onBlur}
        getOptionLabel={getOptionLabel}
        isOptionEqualToValue={isOptionEqualToValue}
        blurOnSelect={blurOnSelect}
        disabled={disabled}
        renderInput={(params) => (
          <TextField
            {...params}
            inputRef={inputRef}
            label={!showLabelAsTypography ? label : undefined}
            placeholder={placeholder}
            helperText={helperText}
            disabled={disabled}
          />
        )}
        renderValue={(tagValue, getTagProps) =>
          tagValue.map((option, index) => {
            const { key, ...tagProps } = getTagProps({ index });
            return (
              <Chip
                aria-description={chipAriaDescription}
                key={key}
                label={getOptionLabel(option)}
                {...tagProps}
                disabled={disabled}
              />
            );
          })
        }
        slotProps={{
          chip: {
            disabled: disabled,
          },
        }}
      />
    </Box>
  );
};

export interface TagInputProps extends BaseTagInputProps {
  value: TagInBook[];
  onChange: (newTags: (TagInBook | string)[]) => void | Promise<void>;
  availableTags?: TagInBook[];
  isProcessing?: boolean;
}

/**
 * Book-tag flavour of {@link TagAutocomplete}: a labelled multi-select over the
 * book's `TagInBook` list. Shared by the highlight dialog and the note editor.
 */
export const TagInput = ({
  value,
  onChange,
  label = 'Tags',
  placeholder = 'Add tags...',
  helperText = 'Press Enter to add a tag, click X to remove',
  disabled = false,
  availableTags = [],
  isProcessing = false,
  chipAriaDescription = 'Selected tag, click to remove',
}: TagInputProps) => {
  const isDisabled = disabled || isProcessing;

  return (
    <TagAutocomplete
      value={value}
      onChange={onChange}
      options={availableTags}
      disabled={isDisabled}
      blurOnSelect={false}
      placeholder={placeholder}
      helperText={helperText}
      preventParentNavigation={true}
      chipAriaDescription={chipAriaDescription}
      getOptionLabel={(option) => (typeof option === 'string' ? option : option.name)}
      isOptionEqualToValue={(option, value) => option.id === value.id}
      label={label}
      showLabelAsTypography={true}
    />
  );
};
