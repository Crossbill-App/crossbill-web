import { expect, onTestFinished, vi } from 'vitest';

/**
 * A clock the test can jump forward. It still runs on with real time, because
 * the navigator's own boot is a chain of timers a frozen clock stalls.
 */
export const fakeTheClock = () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  // Fake timers leave `AbortSignal.timeout` on the real clock.
  const timeout = vi.spyOn(AbortSignal, 'timeout').mockImplementation((ms) => {
    const controller = new AbortController();
    setTimeout(() => controller.abort(new DOMException('signal timed out', 'TimeoutError')), ms);
    return controller.signal;
  });
  onTestFinished(() => {
    timeout.mockRestore();
    vi.useRealTimers();
  });
};

/** The clock moved on until one write has landed. */
export const expectAWriteOnceTheDebounceRunsOut = (writes: unknown[]) =>
  expect
    .poll(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
      return writes.length;
    })
    .toBe(1);
