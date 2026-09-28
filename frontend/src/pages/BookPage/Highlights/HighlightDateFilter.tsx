import { useResetOnChange } from '@/hooks/useResetOnChange.ts';
import {
  DATE_SEARCH_FORMAT,
  getLastSevenDaysFrom,
  isHighlightDateRangeReversed,
  type HighlightDateRange,
} from '@/pages/BookPage/common/highlightDates.ts';
import { SidebarSectionHeader } from '@/pages/BookPage/navigation/SidebarSectionHeader.tsx';
import { CalendarIcon } from '@/theme/Icons.tsx';
import { browserLocale } from '@/utils/date.ts';
import { Box, Button, FormHelperText } from '@mui/material';
import { AdapterLuxon } from '@mui/x-date-pickers/AdapterLuxon';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import type { DateValidationError, PickerChangeHandlerContext } from '@mui/x-date-pickers/models';
import type { TFunction } from 'i18next';
import { DateTime } from 'luxon';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface HighlightDateFilterProps extends HighlightDateRange {
  onChange: (range: HighlightDateRange) => void;
}

const asPickerValue = (value: string | undefined): DateTime | null =>
  value ? DateTime.fromFormat(value, DATE_SEARCH_FORMAT) : null;

const validationMessage = (
  t: TFunction,
  error: DateValidationError | null,
  field: keyof HighlightDateRange,
  oppositeBound: string | undefined
): string | undefined => {
  if (!error) return undefined;
  if (error === 'maxDate' && field === 'from' && oppositeBound)
    return t('highlights.dateFilter.errors.fromAfterTo');
  if (error === 'minDate' && field === 'to' && oppositeBound)
    return t('highlights.dateFilter.errors.toBeforeFrom');
  if (error === 'minDate' || error === 'maxDate')
    return t('highlights.dateFilter.errors.outOfRange');
  return t('highlights.dateFilter.errors.invalid');
};

export const HighlightDateFilter = ({ from, to, onChange }: HighlightDateFilterProps) => {
  const { t } = useTranslation();
  const dateLocale = browserLocale();
  const [fromError, setFromError] = useState<DateValidationError | null>(null);
  const [toError, setToError] = useState<DateValidationError | null>(null);
  const [fromValue, setFromValue] = useState<DateTime<boolean> | null>(() => asPickerValue(from));
  const [toValue, setToValue] = useState<DateTime<boolean> | null>(() => asPickerValue(to));
  const appliedFromValue = asPickerValue(from);
  const appliedToValue = asPickerValue(to);
  const rangeIsReversed = isHighlightDateRangeReversed({ from, to });

  useResetOnChange([from], () => {
    setFromValue(appliedFromValue);
    setFromError(null);
  });
  useResetOnChange([to], () => {
    setToValue(appliedToValue);
    setToError(null);
  });

  const commitDate = (
    key: keyof HighlightDateRange,
    value: DateTime | null,
    context: PickerChangeHandlerContext<DateValidationError>
  ) => {
    if (key === 'from') setFromValue(value);
    else setToValue(value);
    if (context.validationError) return;
    onChange({ from, to, [key]: value?.toFormat(DATE_SEARCH_FORMAT) });
  };

  const applyLastSevenDays = () => {
    const presetFrom = getLastSevenDaysFrom();
    setFromValue(asPickerValue(presetFrom));
    setToValue(null);
    setFromError(null);
    setToError(null);
    onChange({ from: presetFrom, to: undefined });
  };

  return (
    <LocalizationProvider dateAdapter={AdapterLuxon} adapterLocale={dateLocale}>
      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        <SidebarSectionHeader icon={CalendarIcon} title={t('highlights.dateFilter.title')} />
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <DatePicker
            label={t('highlights.dateFilter.from')}
            value={fromValue}
            maxDate={rangeIsReversed ? undefined : (appliedToValue ?? undefined)}
            onChange={(value, context) => commitDate('from', value, context)}
            onError={setFromError}
            slotProps={{
              field: { clearable: true },
              textField: {
                fullWidth: true,
                size: 'small',
                helperText: validationMessage(t, fromError, 'from', to),
              },
            }}
          />
          <DatePicker
            label={t('highlights.dateFilter.to')}
            value={toValue}
            minDate={rangeIsReversed ? undefined : (appliedFromValue ?? undefined)}
            onChange={(value, context) => commitDate('to', value, context)}
            onError={setToError}
            slotProps={{
              field: { clearable: true },
              textField: {
                fullWidth: true,
                size: 'small',
                helperText: validationMessage(t, toError, 'to', from),
              },
            }}
          />
        </Box>
        {rangeIsReversed && (
          <FormHelperText error>{t('highlights.dateFilter.errors.fromAfterTo')}</FormHelperText>
        )}
        <Button
          variant="text"
          size="small"
          sx={{ alignSelf: 'flex-start' }}
          onClick={applyLastSevenDays}
        >
          {t('highlights.dateFilter.lastSevenDays')}
        </Button>
      </Box>
    </LocalizationProvider>
  );
};
