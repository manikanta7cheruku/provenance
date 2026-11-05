import type { ReactNode } from "react";
import { Icon } from "./Icon";

interface NoticeProps {
  tone: "info" | "warn" | "danger";
  title?: string;
  children: ReactNode;
}

/** Inline message. Danger is announced immediately, the others politely. */
export function Notice({ tone, title, children }: NoticeProps) {
  return (
    <div className={`notice notice--${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <span className="notice__icon">
        <Icon name={tone === "info" ? "info" : "alert"} />
      </span>
      <div>
        {title ? <p className="notice__title">{title}</p> : null}
        <div className="notice__body">{children}</div>
      </div>
    </div>
  );
}
