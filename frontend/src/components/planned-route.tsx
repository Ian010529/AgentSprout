import Link from "next/link";

type PlannedRouteProps = {
  eyebrow: string;
  title: string;
  description: string;
  module: string;
};

export function PlannedRoute({ eyebrow, title, description, module }: PlannedRouteProps) {
  return (
    <main className="planned-page">
      <div className="planned-card">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
        <div className="module-note" role="note">
          Planned for {module}. This M1 route does not simulate completed product behavior.
        </div>
        <Link className="text-link" href="/">
          Return to foundation
        </Link>
      </div>
    </main>
  );
}
