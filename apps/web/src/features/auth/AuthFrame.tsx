import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { BrandMark, PageHeader } from "../../ui";
import "./auth.css";

interface AuthFrameProps {
  title: string;
  description?: string;
  children: ReactNode;
}

/** The sign-in family of screens: one small card in the middle of a quiet page. */
export function AuthFrame({ title, description, children }: AuthFrameProps) {
  return (
    <div className="auth">
      <main id="main" className="auth__card">
        <p className="auth__brand">
          <BrandMark size={24} />
          Provenance
        </p>
        <PageHeader title={title} {...(description ? { description } : {})} />
        {children}
        <p className="auth__legal">
          <Link to="/privacy">Privacy policy</Link> <Link to="/terms">Terms of use</Link>
        </p>
      </main>
    </div>
  );
}
