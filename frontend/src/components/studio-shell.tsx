import Link from "next/link";
import type { ReactNode } from "react";

import type { Role } from "@/lib/api";

export type StudioSection = "workshop" | "reviews" | "published";

type StudioShellProps = {
  role: Role;
  activeSection?: StudioSection;
  busy?: boolean;
  children: ReactNode;
  onRoleChange: (role: Role) => void;
  onSignOut: () => void;
};

const STUDIO_NAV: Array<{ id: StudioSection; number: string; label: string; href: string }> = [
  { id: "workshop", number: "01", label: "Workshop", href: "/studio" },
  { id: "reviews", number: "02", label: "Reviews", href: "/studio/reviews" },
  { id: "published", number: "03", label: "Published", href: "/studio/published" },
];

export function StudioShell({ role, activeSection = "workshop", busy, children, onRoleChange, onSignOut }: StudioShellProps) {
  return (
    <div className="studio-frame">
      <aside className="studio-sidebar">
        <Link className="wordmark" href="/studio" aria-label="AgentSprout dashboard">
          <span className="sprout-mark" aria-hidden="true">
            <i />
            <i />
          </span>
          AgentSprout
        </Link>
        <nav aria-label="Studio navigation">
          {STUDIO_NAV.map((item) => (
            <Link
              key={item.id}
              className={`studio-nav-link${activeSection === item.id ? " studio-nav-link--active" : ""}`}
              href={item.href}
              aria-current={activeSection === item.id ? "page" : undefined}
            >
              <span aria-hidden="true">{item.number}</span> {item.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-note">
          <p>Concept build</p>
          <strong>Responsible agents, made visible.</strong>
        </div>
      </aside>
      <div className="studio-column">
        <header className="studio-header">
          <div>
            <span className="status-pin" aria-hidden="true" /> Studio connected
          </div>
          <div className="role-controls" aria-label="Demo role">
            <span>View as</span>
            <button
              type="button"
              className={role === "STUDENT" ? "is-selected" : ""}
              disabled={busy}
              aria-pressed={role === "STUDENT"}
              onClick={() => onRoleChange("STUDENT")}
            >
              Student
            </button>
            <button
              type="button"
              className={role === "TEACHER" ? "is-selected" : ""}
              disabled={busy}
              aria-pressed={role === "TEACHER"}
              onClick={() => onRoleChange("TEACHER")}
            >
              Teacher
            </button>
            <button className="sign-out" type="button" disabled={busy} onClick={onSignOut}>
              Sign out
            </button>
          </div>
        </header>
        {children}
      </div>
      <div className="studio-device-message" role="note">
        <span className="sprout-mark" aria-hidden="true">
          <i />
          <i />
        </span>
        <h1>Continue on a wider screen.</h1>
        <p>The Agent workshop is designed for a laptop or a tablet in landscape, at least 1024px wide.</p>
        <Link href="/">Return to the concept</Link>
      </div>
    </div>
  );
}
