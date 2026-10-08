import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { fetchStatus, type ApiStatus } from "./api";

export type SystemState =
  | { kind: "loading" }
  | { kind: "unreachable"; message: string }
  | { kind: "loaded"; status: ApiStatus };

interface SystemStatusValue {
  state: SystemState;
  refresh: () => void;
}

const SystemStatusContext = createContext<SystemStatusValue | null>(null);

/** Holds the API status for the whole app. Infrastructure: it renders no UI of its own. */
export function SystemStatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SystemState>({ kind: "loading" });
  const controllerRef = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState({ kind: "loading" });
    fetchStatus(controller.signal)
      .then((status) => setState({ kind: "loaded", status }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "unreachable",
          message: error instanceof Error ? error.message : "Unknown error.",
        });
      });
  }, []);

  useEffect(() => {
    refresh();
    return () => controllerRef.current?.abort();
  }, [refresh]);

  return (
    <SystemStatusContext.Provider value={{ state, refresh }}>
      {children}
    </SystemStatusContext.Provider>
  );
}

export function useSystemStatus(): SystemStatusValue {
  const value = useContext(SystemStatusContext);
  if (!value) throw new Error("useSystemStatus must be used inside SystemStatusProvider");
  return value;
}
