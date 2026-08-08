import { Typography } from '@mui/material';

export const PageTitle = ({ text }: { text: string }) => {
  return (
    <Typography variant="h1" component="h2" gutterBottom sx={{ color: 'primary.main', mb: 2 }}>
      {text}
    </Typography>
  );
};
