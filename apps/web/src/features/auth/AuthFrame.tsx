import type { ReactNode } from "react";
import { PageHeader } from "../../ui";
import "./auth.css";

interface AuthFrameProps {
  title: string;
  description?: string;
  children: ReactNode;
}

export function AuthFrame({ title, description, children }: AuthFrameProps) {
  return (
    <main id="main" className="auth">
      <p className="auth__brand">Provenance</p>
      <PageHeader title={title} {...(description ? { description } : {})} />
      {children}
    </main>
  );
}
