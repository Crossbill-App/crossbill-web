/* eslint-disable */
// PROTOTYPE — throwaway. Lives on branch prototype/landing-due-cards only.
import { Box, IconButton, Typography } from '@mui/material';
import { useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';

interface PrototypeSwitcherProps {
  variants: { key: string; name: string }[];
  current: string;
}

const isTyping = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));

export const PrototypeSwitcher = ({ variants, current }: PrototypeSwitcherProps) => {
  const navigate = useNavigate();
  const index = Math.max(
    0,
    variants.findIndex((v) => v.key === current)
  );

  const go = (step: number) => {
    const next = variants[(index + step + variants.length) % variants.length];
    void navigate({
      to: '.',
      search: (prev: object) => ({ ...prev, variant: next.key }),
      replace: true,
    });
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === 'ArrowLeft') go(-1);
      if (event.key === 'ArrowRight') go(1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  if (!import.meta.env.DEV) return null;

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: 24,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 2000,
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        px: 1,
        py: 0.5,
        borderRadius: 999,
        bgcolor: '#111',
        color: '#fff',
        boxShadow: '0 6px 24px rgba(0,0,0,0.35)',
        fontFamily: 'monospace',
      }}
    >
      <IconButton size="small" onClick={() => go(-1)} sx={{ color: '#fff' }}>
        ‹
      </IconButton>
      <Typography
        sx={{ fontFamily: 'monospace', fontSize: 14, minWidth: 280, textAlign: 'center' }}
      >
        PROTOTYPE {variants[index].key} — {variants[index].name}
      </Typography>
      <IconButton size="small" onClick={() => go(1)} sx={{ color: '#fff' }}>
        ›
      </IconButton>
    </Box>
  );
};
