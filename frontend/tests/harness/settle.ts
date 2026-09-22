import type { QueryClient } from '@tanstack/react-query';
import { expect } from 'vitest';
import { cleanup } from 'vitest-browser-react';

/** `count` animation frames gone by: what a render or a scroll lands on. */
export const afterFrames = async (count = 2) => {
  for (let frame = 0; frame < count; frame++) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
};

/**
 * Every request on `client` answered but the `held` ones, and two frames for
 * the answers to render.
 *
 * What a test proving that something did *not* happen waits on: the absence
 * it asserts is then an answer acted on, not one still on its way. A frame
 * goes by first, since a request can start a tick after what asked for it.
 */
export const afterTheAnswersRender = async (client: QueryClient, { held = 0 } = {}) => {
  await afterFrames(1);
  await expect.poll(() => client.isFetching() + client.isMutating()).toBe(held);
  await afterFrames(2);
};

/**
 * Unmounts, then waits until every `fetch` the unmount sent is answered.
 *
 * A reader leaving a book writes where it was with a `keepalive` fetch sent
 * from the unmount itself, outside any query client. Waiting on that request
 * is what lands the write on the handlers of the test that made it, and what
 * lets a test prove that no such write went out.
 */
export const unmountAndAwaitItsWrites = async (unmount: () => void = cleanup) => {
  const sent: Promise<Response>[] = [];
  const realFetch = window.fetch;
  window.fetch = (...args) => {
    const request = realFetch(...args);
    sent.push(request);
    return request;
  };
  try {
    unmount();
  } finally {
    window.fetch = realFetch;
  }
  await Promise.allSettled(sent);
};
