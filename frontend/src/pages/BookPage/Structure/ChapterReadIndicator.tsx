import { useTheme } from '@mui/material';
import { useTranslation } from 'react-i18next';

type ReadStatus = 'read' | 'current' | 'unread';

interface ChapterReadIndicatorProps {
  status: ReadStatus;
  /** Chapter this indicator belongs to, folded into the accessible name so a
   * test (or a screen reader) can tell which chapter is "current". */
  chapterName: string;
}

const SIZE = 20;

export const ChapterReadIndicator = ({ status, chapterName }: ChapterReadIndicatorProps) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const brown = theme.palette.secondary.dark;
  const gray = theme.palette.text.disabled;

  return (
    <svg
      role="img"
      aria-label={t(`structure.chapterReadIndicator.${status}`, { chapterName })}
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      style={{ flexShrink: 0, display: 'block' }}
    >
      {status === 'read' && (
        <>
          <circle cx={10} cy={10} r={8} fill={brown} />
          <path
            d="M6 10.5 L9 13.5 L14.5 7"
            fill="none"
            stroke="white"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
      {status === 'current' && (
        <>
          <circle cx={10} cy={10} r={7.5} fill="none" stroke={brown} strokeWidth={1.5} />
          <circle cx={10} cy={10} r={3.5} fill={brown} />
        </>
      )}
      {status === 'unread' && (
        <circle cx={10} cy={10} r={7.5} fill="none" stroke={gray} strokeWidth={1.5} />
      )}
    </svg>
  );
};
