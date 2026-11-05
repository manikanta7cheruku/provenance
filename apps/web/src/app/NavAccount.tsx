import { useNavigate } from "react-router-dom";
import { useSession } from "../lib/session";
import { Button } from "../ui";

/** Who is signed in, and the way out. Lives at the foot of the navigation. */
export function NavAccount() {
  const session = useSession();
  const navigate = useNavigate();
  if (session.state.kind !== "authenticated") return null;
  const { email } = session.state.user;
  const initial = (email[0] ?? "?").toUpperCase();

  async function onSignOut() {
    await session.signOut();
    navigate("/signin", { replace: true });
  }

  return (
    <div className="shell__account">
      <span className="shell__avatar" aria-hidden="true">
        {initial}
      </span>
      <p className="shell__account-email" title={email}>
        {email}
      </p>
      <Button variant="ghost" onClick={() => void onSignOut()}>
        Sign out
      </Button>
    </div>
  );
}
