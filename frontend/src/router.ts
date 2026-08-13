import { routeTree } from './routeTree.gen';

/**
 * The router options the app runs on, shared with the test harness so a test
 * drives the same router the browser does.
 *
 * `scrollRestoration` is what makes going back keep the position the page was
 * left at. Without it the router scrolls to the top on every navigation it
 * renders, popstate included — and a dialog that lives in a search param
 * (`useUrlEntityDialog`) closes itself with `history.back()`, so closing one
 * threw the page underneath back to the top.
 */
export const routerOptions = {
  routeTree,
  scrollRestoration: true,
} as const;
