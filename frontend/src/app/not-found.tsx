import Link from "next/link";

export default function NotFound() {
  return (
    <main className="planned-page">
      <div className="planned-card">
        <p className="eyebrow">404 · Off the map</p>
        <h1>This route is outside the expedition.</h1>
        <p>The page may not exist, or it may not be available to this visitor.</p>
        <Link className="text-link" href="/">
          Return to AgentSprout
        </Link>
      </div>
    </main>
  );
}
