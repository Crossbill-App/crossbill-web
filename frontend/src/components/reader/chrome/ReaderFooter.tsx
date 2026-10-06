import type { EbookChapterProgress } from '@/components/reader/engine/EbookReader.ts';
import type { readerPageColors } from '@/components/reader/preferences/readerPreferences.ts';
import { BookCoverIcon, PagesLeftIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { tabularNums } from '@/theme/theme.ts';
import { alpha, Box, Stack, Typography, type SvgIconProps } from '@mui/material';
import type { ComponentType } from 'react';
import { useTranslation } from 'react-i18next';

export interface ReaderFooterProps {
  progression: number | undefined;
  chapterProgress: EbookChapterProgress | null;
  colors: ReturnType<typeof readerPageColors>;
}

interface FooterStatProps {
  Icon: ComponentType<SvgIconProps>;
  /** What the number means: the icon says it to the eye, this to a screen reader. */
  label: string;
  value: string;
  colors: ReturnType<typeof readerPageColors>;
}

const FooterStat = ({ Icon, label, value, colors }: FooterStatProps) => (
  // 0.7 of the page's own text, which is 6.3:1 on the light page
  // and 8.4:1 on the dark one; body text needs 4.5:1.
  <Stack
    direction="row"
    spacing={0.5}
    sx={{ alignItems: 'center', color: alpha(colors.text, 0.7) }}
  >
    <Icon titleAccess={label} sx={{ fontSize: ICON_SIZE.inline }} />
    <Typography variant="body2" noWrap sx={tabularNums}>
      {value}
    </Typography>
  </Stack>
);

/** The strip under the page: how much of the chapter is left, and how far into the book. */
export const ReaderFooter = ({ progression, chapterProgress, colors }: ReaderFooterProps) => {
  const { t } = useTranslation();

  return (
    <Box
      component="footer"
      sx={{
        display: 'flex',
        alignItems: 'center',
        // Centred on both axes: a phone's rounded corners would clip or crowd
        // stats pushed to an edge. The extra height clears an iPhone's home
        // indicator, which the page runs under, and the stats sit in the
        // middle of the whole strip rather than above the inset.
        justifyContent: 'center',
        gap: 2,
        // Held open before the position is known, so the page is not laid out
        // twice when the label arrives.
        minHeight: 'calc(32px + env(safe-area-inset-bottom))',
        px: 2,
        borderTop: 1,
        borderColor: alpha(colors.text, 0.12),
      }}
    >
      <Box>
        {chapterProgress && (
          <FooterStat
            Icon={PagesLeftIcon}
            label={t('reader.footer.pagesLeftInChapter')}
            value={String(chapterProgress.pagesLeft)}
            colors={colors}
          />
        )}
      </Box>
      <Box>
        {progression !== undefined && (
          <FooterStat
            Icon={BookCoverIcon}
            label={t('reader.footer.readOfBook')}
            value={`${Math.round(progression * 100)}%`}
            colors={colors}
          />
        )}
      </Box>
    </Box>
  );
};
