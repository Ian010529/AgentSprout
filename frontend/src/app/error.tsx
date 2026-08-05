"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="planned-page">
      <div className="planned-card">
        <p className="eyebrow">Application error</p>
        <h1>The workshop hit an unexpected problem.</h1>
        <p>No secret or provider detail is displayed here. Try the route again, or return home.</p>
        <div className="error-actions">
          <button className="primary-button" type="button" onClick={reset}>
            Try again
          </button>
          <Link className="text-link" href="/">
            Return home
          </Link>
        </div>
      </div>
    </main>
  );
}
