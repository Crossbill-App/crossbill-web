import { useState } from 'react';

/**
 * Re-initialises local state during render whenever `deps` change.
 *
 * This is the React-documented replacement for the `useEffect(() => setX(prop),
 * [prop])` idiom that `react-hooks/set-state-in-effect` rejects: resetting in an
 * effect renders once with the stale value, commits, then renders again, so the
 * old value can be painted before the correction lands. Adjusting during render
 * makes React discard the in-progress output and re-run the component before
 * anything reaches the screen.
 *
 * `deps` are compared with `Object.is`, exactly like effect dependencies, so
 * call sites translate one-for-one from the effects they replace.
 */
export const useResetOnChange = (deps: unknown[], reset: () => void): void => {
  const [prevDeps, setPrevDeps] = useState(deps);

  const changed =
    deps.length !== prevDeps.length || deps.some((dep, i) => !Object.is(dep, prevDeps[i]));

  if (changed) {
    setPrevDeps(deps);
    reset();
  }
};
