import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { BrandMark, PageHeader } from "../../ui";
import "./auth.css";

interface AuthFrameProps {
  title: string;
  description?: string;
  children: ReactNode;
}

/** The sign-in family of screens: the form on one side and, on wide screens, what the product stands for. */
export function AuthFrame({ title, description, children }: AuthFrameProps) {
  return (
    <div className="auth-shell">
      <main id="main" className="auth">
        <p className="auth__brand">
          <BrandMark size={32} />
          Provenance
        </p>
        <PageHeader title={title} {...(description ? { description } : {})} />
        {children}
        <p className="auth__legal">
          <Link to="/privacy">Privacy policy</Link> <Link to="/terms">Terms of use</Link>
        </p>
      </main>
      <aside className="auth-panel" aria-label="About Provenance">
        <p className="auth-panel__line">Jobs, with receipts.</p>
        <ul className="auth-panel__points">
          <li>
            <strong>Every claim has a source.</strong> A match points back to the line of your evidence and the line of the posting it came from.
          </li>
          <li>
            <strong>Nothing is sent for you.</strong> Drafts are yours to check and to send.
          </li>
          <li>
            <strong>Your documents stay private.</strong> Only you can open them, and you can delete them any time.
          </li>
        </ul>
      </aside>
    </div>
  );
}
