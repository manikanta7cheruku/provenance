import { useCallback, useEffect, useRef, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  /** True only before the first result. Later refreshes keep showing the old data. */
  loading: boolean;
  refreshing: boolean;
  reload: () => void;
}

/**
 * Loads data and exposes loading, error and reload. Requests are cancelled when the inputs
 * change or the screen goes away, so a slow old answer can never overwrite a newer one.
 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    const controller = new AbortController();
    setRefreshing(true);
    loadRef
      .current(controller.signal)
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught : new Error("Unknown error."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setRefreshing(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { data, error, loading: data === null && error === null, refreshing, reload };
}
