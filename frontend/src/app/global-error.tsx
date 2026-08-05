"use client";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <html lang="en">
      <body>
        <main className="planned-page">
          <div className="planned-card">
            <p className="eyebrow">AgentSprout error</p>
            <h1>The application could not open safely.</h1>
            <p>Try loading the application again.</p>
            <button className="primary-button" type="button" onClick={reset}>
              Try again
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
