/** Share one in-flight async operation and allow a later retry after it settles. */
export function runSingleFlight<T>(
  pending: { current: Promise<T> | null },
  task: () => Promise<T>
): Promise<T> {
  if (pending.current) return pending.current;

  const operation = Promise.resolve().then(task);
  pending.current = operation;

  const clearIfCurrent = () => {
    if (pending.current === operation) pending.current = null;
  };
  void operation.then(clearIfCurrent, clearIfCurrent);

  return operation;
}
