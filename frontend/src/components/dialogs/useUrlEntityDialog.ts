import { useNavigate, useSearch } from '@tanstack/react-router';
import { useCallback, useMemo, useRef, useState } from 'react';

export interface UseUrlEntityDialogOptions<T extends { id: number }> {
  /** Search-param key holding the open entity's id, e.g. `highlightId`. */
  param: string;
  /** Ordered list backing index/entity resolution and prev/next navigation. */
  items?: T[];
  syncToUrl?: boolean;
}

export interface UrlEntityDialogController<T extends { id: number }> {
  activeId: number | null;
  /** Index of the active entity in `items`; -1 when it is not in the list. */
  activeIndex: number;
  activeItem: T | null;
  totalCount: number;
  open: (id: number) => void;
  close: () => void;
  navigateToIndex: (index: number) => void;
}

export const useUrlEntityDialog = <T extends { id: number }>({
  param,
  items = [],
  syncToUrl = true,
}: UseUrlEntityDialogOptions<T>): UrlEntityDialogController<T> => {
  // strict: false so this hook works from any child route under /book/$bookId
  const search = useSearch({ strict: false }) as Record<string, number | undefined>;
  // Navigate on the current route — search params vary by route, but the
  // dialog param is a validated param wherever the dialog is used.
  const navigate = useNavigate() as (opts: {
    search: (prev: Record<string, unknown>) => Record<string, unknown>;
    replace?: boolean;
    resetScroll?: boolean;
  }) => Promise<void>;

  // Tracks whether the dialog was opened via user click (push) vs direct URL
  const wasOpenedByPush = useRef(false);

  // Local state used when syncToUrl is false
  const [localId, setLocalId] = useState<number | null>(null);

  // URL is the source of truth when syncToUrl is true, otherwise local state
  const activeId = syncToUrl ? (search[param] ?? null) : localId;

  const setActiveId = useCallback(
    (newId: number | undefined, replace: boolean) => {
      if (syncToUrl) {
        void navigate({
          search: (prev) => ({ ...prev, [param]: newId }),
          replace,
          // The page underneath does not change, so neither should its scroll
          // position — the router resets it to the top by default.
          resetScroll: false,
        });
      } else {
        setLocalId(newId ?? null);
      }
    },
    [navigate, param, syncToUrl]
  );

  // Push to history so the back button closes the dialog
  const open = useCallback(
    (id: number) => {
      wasOpenedByPush.current = true;
      setActiveId(id, false);
    },
    [setActiveId]
  );

  // Pop history entry if opened via push, otherwise replace
  const close = useCallback(() => {
    if (wasOpenedByPush.current && syncToUrl) {
      wasOpenedByPush.current = false;
      window.history.back();
    } else {
      setActiveId(undefined, true);
    }
  }, [setActiveId, syncToUrl]);

  // Replace so back goes to the pre-dialog state, not the previous entity
  const navigateToIndex = useCallback(
    (index: number) => {
      setActiveId(items[index].id, true);
    },
    [items, setActiveId]
  );

  const activeIndex = useMemo(
    () => (activeId === null ? -1 : items.findIndex((item) => item.id === activeId)),
    [items, activeId]
  );

  const activeItem = activeIndex === -1 ? null : items[activeIndex];

  return {
    activeId,
    activeIndex,
    activeItem,
    totalCount: items.length,
    open,
    close,
    navigateToIndex,
  };
};
