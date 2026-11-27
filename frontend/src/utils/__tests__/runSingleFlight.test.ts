import { describe, expect, it, vi } from 'vitest';
import { runSingleFlight } from '../runSingleFlight';

describe('runSingleFlight', () => {
  it('shares an in-flight operation and permits retry after it settles', async () => {
    const pending: { current: Promise<string> | null } = { current: null };
    let finishFirst!: (value: string) => void;
    const firstTask = vi.fn(() => new Promise<string>(resolve => {
      finishFirst = resolve;
    }));

    const first = runSingleFlight(pending, firstTask);
    const duplicate = runSingleFlight(pending, firstTask);

    expect(duplicate).toBe(first);
    expect(firstTask).toHaveBeenCalledTimes(0);

    await Promise.resolve();
    expect(firstTask).toHaveBeenCalledTimes(1);
    finishFirst('avatar ready');
    await expect(first).resolves.toBe('avatar ready');

    const retry = runSingleFlight(pending, async () => 'retry');
    await expect(retry).resolves.toBe('retry');
    expect(pending.current).toBeNull();
  });
});
