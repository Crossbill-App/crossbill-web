import { useSettings } from '@/context/SettingsContext';
import { ExternalLinkIcon } from '@/theme/Icons.tsx';
import { Box, Divider, Link, Typography } from '@mui/material';

const REPOSITORY_URL = 'https://github.com/Crossbill-App/crossbill-web';
const DOCUMENTATION_URL = 'https://crossbill-app.github.io/crossbill-web/';
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
  const { settings } = useSettings();
  const version = settings?.version ?? UNKNOWN_VERSION;

  return (
    <Box sx={{ mt: 6 }}>
      <Typography variant="h3" sx={{ mb: 3, color: 'text.primary' }}>
        About
      </Typography>

      <Divider sx={{ mb: 3 }} />

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          columnGap: 3,
          rowGap: 1.5,
          alignItems: 'start',
        }}
      >
        <Row label="Version">
          {version === UNKNOWN_VERSION ? (
            <Typography variant="body2" sx={{ color: 'text.primary' }}>
              {UNKNOWN_VERSION}
            </Typography>
          ) : (
            <ExternalValue href={`${REPOSITORY_URL}/releases/tag/v${version}`}>
              {`v${version}`}
            </ExternalValue>
          )}
        </Row>

        <Row label="Documentation">
          <ExternalValue href={DOCUMENTATION_URL}>
            crossbill-app.github.io/crossbill-web
          </ExternalValue>
        </Row>

        <Row label="Source code">
          <ExternalValue href={REPOSITORY_URL}>
            github.com/Crossbill-App/crossbill-web
          </ExternalValue>
        </Row>
      </Box>
    </Box>
  );
};
