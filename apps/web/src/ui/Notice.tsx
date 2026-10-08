import type { ReactNode } from "react";

interface NoticeProps {
  tone: "info" | "warn" | "danger";
  title?: string;
  children: ReactNode;
}

/** Inline message. Danger is announced immediately, the others politely. */
export function Notice({ tone, title, children }: NoticeProps) {
  return (
    <div className={`notice notice--${tone}`} role={tone === "danger" ? "alert" : "status"}>
      {title ? <p className="notice__title">{title}</p> : null}
      <div className="notice__body">{children}</div>
    </div>
  );
}
