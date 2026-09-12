import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { Box, ToggleButton, ToggleButtonGroup } from '@mui/material';

interface ChoiceSectionProps<Option extends string> {
  /** The heading above the control, and the group's accessible name. */
  heading: string;
  options: readonly Option[];
  labels: Record<Option, string>;
  value: Option;
  onSelect: (option: Option) => void;
}

/** A headed row of choices, one of which is always the chosen one. */
export const ChoiceSection = <Option extends string>({
  heading,
  options,
  labels,
  value,
  onSelect,
}: ChoiceSectionProps<Option>) => (
  <Box>
    <SectionTitle>{heading}</SectionTitle>
    <ToggleButtonGroup
      exclusive
      fullWidth
      size="small"
      value={value}
      aria-label={heading}
      onChange={(_event, chosen: Option | null) => {
        // Null when the button pressed was the active one already, and every
        // one of these settings always has a value.
        if (chosen !== null) onSelect(chosen);
      }}
    >
      {options.map((option) => (
        <ToggleButton key={option} value={option}>
          {labels[option]}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  </Box>
);
