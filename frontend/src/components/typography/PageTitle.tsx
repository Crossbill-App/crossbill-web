import { Typography } from '@mui/material';

interface PageTitleProps {
  text: string;
  /**
   * A page whose title *is* its name — Settings, the library, the auth screens
   * — is an `h1`. A tab sitting under a book's own title stays an `h2`, which
   * is why that is the default.
   */
  component?: 'h1' | 'h2';
}

/** The heading every page leads with. Inherits `text-align` from its parent. */
export const PageTitle = ({ text, component = 'h2' }: PageTitleProps) => (
  <Typography
    variant="h2"
    component={component}
    gutterBottom
    sx={{ color: 'primary.main', mb: 2, fontWeight: 900 }}
  >
    {text}
  </Typography>
);
