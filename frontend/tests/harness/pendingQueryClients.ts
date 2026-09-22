import type { QueryClient } from '@tanstack/react-query';

/**
 * Every `QueryClient` a test has created since the last drain.
 *
 * A component can still have a request in flight for a moment after the test
 * that triggered it has moved on — opening a dialog fires a fetch nothing in
 * the test awaits, for instance. `tests/setup.ts`'s `afterEach` drains this
 * list and gives each client a bounded chance to go idle before resetting MSW
 * handlers, so that request lands on the handlers that were active when it
 * was made rather than being orphaned onto whichever later test's `afterEach`
 * happens to run when it finally resolves.
 */
export const pendingQueryClients: QueryClient[] = [];
