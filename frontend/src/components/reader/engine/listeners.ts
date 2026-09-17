/** One event's listeners, and the ways they are added to, rung and let go of. */
interface ListenerSet<T> {
  add(listener: (value: T) => void): () => void;
  notify(value: T): void;
  clear(): void;
}

/** The listeners waiting on one event of a reader, which an engine keeps one of per event. */
export const listenerSet = <T>(): ListenerSet<T> => {
  const listeners = new Set<(value: T) => void>();
  return {
    add: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    notify: (value) => {
      // Over a copy: a subscriber let go of while the set is being rung is still
      // owed this one, and the walk must reach whoever comes after it.
      for (const listener of [...listeners]) {
        try {
          listener(value);
        } catch {
          // A subscriber that throws must not reject Readium's in-flight navigation.
        }
      }
    },
    clear: () => listeners.clear(),
  };
};
