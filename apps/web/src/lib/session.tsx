import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { setCsrfToken, setUnauthorizedHandler } from "./api";
import type { AuthConfig, SessionResponse, SessionUser } from "./api";
import * as authApi from "./auth-api";

const DEFAULT_CONFIG: AuthConfig = { signup_mode: "invite", email_verification_required: false };

export type SessionState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "anonymous"; config: AuthConfig; expired: boolean }
  | { kind: "authenticated"; user: SessionUser; config: AuthConfig };

interface SessionValue {
  state: SessionState;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, inviteCode: string | null) => Promise<void>;
  signOut: () => Promise<void>;
  /** Adopt a session returned by another call (for example after a password change). */
  adopt: (response: SessionResponse) => void;
}

const SessionContext = createContext<SessionValue | null>(null);

/** Holds who is signed in. Infrastructure: it renders no UI of its own. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ kind: "loading" });

  const adopt = useCallback((response: SessionResponse) => {
    setCsrfToken(response.csrf_token);
    if (response.authenticated && response.user) {
      setState({ kind: "authenticated", user: response.user, config: response.config });
    } else {
      setState({ kind: "anonymous", config: response.config, expired: false });
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      adopt(await authApi.getSession());
    } catch (error) {
      setState({
        kind: "error",
        message: error instanceof Error ? error.message : "Unknown error.",
      });
    }
  }, [adopt]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // When the server says the session ended, show the sign-in page with an explanation.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setCsrfToken(null);
      setState((previous) => ({
        kind: "anonymous",
        config: "config" in previous ? previous.config : DEFAULT_CONFIG,
        expired: true,
      }));
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      adopt(await authApi.login(email, password));
    },
    [adopt],
  );
  const signUp = useCallback(
    async (email: string, password: string, inviteCode: string | null) => {
      adopt(await authApi.register(email, password, inviteCode));
    },
    [adopt],
  );
  const signOut = useCallback(async () => {
    adopt(await authApi.logout());
  }, [adopt]);

  return (
    <SessionContext.Provider value={{ state, refresh, signIn, signUp, signOut, adopt }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
