import { NotOnDeviceIcon } from '@/theme/Icons.tsx';
import { Chip, Tooltip } from '@mui/material';

interface NotOnDeviceChipProps {
  removed: boolean | undefined;
  size?: 'small' | 'medium';
}

export const NotOnDeviceChip = ({ removed, size = 'small' }: NotOnDeviceChipProps) => {
  if (!removed) {
    return null;
  }

  return (
    <Tooltip title="Deleted on the e-reader.">
      <Chip
        size="small"
        variant="outlined"
        icon={<NotOnDeviceIcon />}
        sx={{
          color: 'text.secondary',
          borderColor: 'divider',
          fontWeight: 500,
          paddingLeft: '8px',
          fontSize: size === 'small' ? '0.7rem' : '0.8rem',
          height: size === 'small' ? 22 : 26,
          '& .MuiChip-icon': {
            color: 'text.secondary',
            fontSize: size === 'small' ? 14 : 16,
          },
        }}
      />
    </Tooltip>
  );
};
