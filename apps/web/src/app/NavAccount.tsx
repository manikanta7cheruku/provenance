import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../lib/session";
import { Button } from "../ui";
import { NavStatus } from "./NavStatus";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Who is signed in, the appearance choice, system status and the way out. On wide screens it is a
 * small menu behind the avatar; in the phone sheet it is simply shown.
 */
export function NavAccount() {
  const session = useSession();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (session.state.kind !== "authenticated") return null;
  const { email } = session.state.user;
  const initial = (email[0] ?? "?").toUpperCase();

  async function onSignOut() {
    await session.signOut();
    navigate("/signin", { replace: true });
  }

  return (
    <div className="account" ref={root}>
      <button
        type="button"
        className="account__button"
        aria-label="Account menu"
        aria-expanded={open}
        aria-controls="account-panel"
        onClick={() => setOpen((value) => !value)}
      >
        {initial}
      </button>
      <div id="account-panel" className="account__panel" data-open={open}>
        <p className="account__email" title={email}>
          {email}
        </p>
        <div className="account__row">
          <ThemeToggle />
        </div>
        <div className="account__row">
          <NavStatus />
        </div>
        <Button onClick={() => void onSignOut()}>Sign out</Button>
      </div>
    </div>
  );
}
