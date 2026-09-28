import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { useSettings } from '@/context/SettingsContext';
import { ExternalLinkIcon } from '@/theme/Icons.tsx';
import { Box, Link, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

const REPOSITORY_URL = 'https://github.com/Crossbill-App/crossbill-web';
const DOCUMENTATION_URL = 'https://crossbill-app.github.io/crossbill-web/';
/** The version `SettingsContext` reports when the server could not be asked. */
const UNKNOWN_VERSION = 'unknown';

const ExternalValue = ({ href, children }: { href: string; children: string }) => (
  <Link
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    variant="body2"
    sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, overflowWrap: 'anywhere' }}
  >
    {children}
    <ExternalLinkIcon sx={{ fontSize: '0.9rem' }} />
  </Link>
);

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <>
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
      {label}
    </Typography>
    {children}
  </>
);

export const AboutSection = () => {
  const { t } = useTranslation();
  const { settings } = useSettings();
  const version = settings?.version ?? UNKNOWN_VERSION;

  return (
    <Box sx={{ mt: 6 }}>
      <SectionTitle showDivider>{t('settings.about.title')}</SectionTitle>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          columnGap: 3,
          rowGap: 1.5,
          alignItems: 'start',
        }}
      >
        <Row label={t('settings.about.version')}>
          {version === UNKNOWN_VERSION ? (
            <Typography variant="body2" sx={{ color: 'text.primary' }}>
              {t('settings.about.unknownVersion')}
            </Typography>
          ) : (
            <ExternalValue href={`${REPOSITORY_URL}/releases/tag/v${version}`}>
              {`v${version}`}
            </ExternalValue>
          )}
        </Row>

        <Row label={t('settings.about.documentation')}>
          <ExternalValue href={DOCUMENTATION_URL}>
            {t('settings.about.documentationLink')}
          </ExternalValue>
        </Row>

        <Row label={t('settings.about.sourceCode')}>
          <ExternalValue href={REPOSITORY_URL}>{t('settings.about.sourceCodeLink')}</ExternalValue>
        </Row>
      </Box>
    </Box>
  );
};
