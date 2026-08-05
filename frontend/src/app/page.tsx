import Link from "next/link";

import { SystemStatus } from "@/components/system-status";

const workflow = [
  { number: "01", title: "Define", copy: "Shape a useful agent around a real learner need." },
  { number: "02", title: "Test", copy: "Try evidence, safety boundaries, and age-appropriate responses." },
  { number: "03", title: "Reflect", copy: "Use teacher evaluation to understand what should improve." },
  { number: "04", title: "Publish", copy: "Share only an approved, evaluated agent version." },
];

export default function Home() {
  return (
    <div className="site-shell">
      <header className="topbar">
        <Link className="wordmark" href="/" aria-label="AgentSprout Studio home">
          <span className="sprout-mark" aria-hidden="true">
            <i />
            <i />
          </span>
          AgentSprout
        </Link>
        <div className="topbar-meta">
          <span className="environment-pill">Foundation · M1</span>
          <Link className="nav-link" href="/access">
            Enter Studio
          </Link>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">A learning workshop for responsible AI</p>
            <h1>
              Build agents that can <em>earn</em> their way to launch.
            </h1>
            <p className="hero-lede">
              Students turn knowledge into working agents. Teachers evaluate the evidence, safety,
              and choices behind every version before it is shared.
            </p>
            <div className="hero-actions">
              <Link className="primary-button" href="/access">
                Explore the Studio
              </Link>
              <a className="secondary-link" href="#how-it-works">
                See the learning loop <span aria-hidden="true">↓</span>
              </a>
            </div>
          </div>

          <aside className="field-note" aria-label="Ocean Explorer preview">
            <div className="field-note-header">
              <span>Field note 001</span>
              <span>Knowledge Explorer</span>
            </div>
            <div className="ocean-orbit" aria-hidden="true">
              <span className="orbit orbit-one" />
              <span className="orbit orbit-two" />
              <span className="ocean-core">OE</span>
            </div>
            <p className="field-note-kicker">First expedition</p>
            <h2>Ocean Explorer</h2>
            <p>
              A grounded agent that answers from NOAA ocean-literacy material and knows when to
              guide, block, or say it lacks evidence.
            </p>
            <div className="field-note-tags">
              <span>RAG evidence</span>
              <span>Age-aware</span>
              <span>Teacher tested</span>
            </div>
          </aside>
        </section>

        <section className="workflow-section" id="how-it-works" aria-labelledby="workflow-title">
          <div className="section-heading">
            <p className="eyebrow">The learning loop</p>
            <h2 id="workflow-title">From idea to accountable agent.</h2>
          </div>
          <ol className="workflow-grid">
            {workflow.map((step) => (
              <li key={step.number}>
                <span>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.copy}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="foundation-section" aria-labelledby="foundation-title">
          <div>
            <p className="eyebrow">M1 foundation</p>
            <h2 id="foundation-title">The workshop has an honest heartbeat.</h2>
            <p>
              This first module proves the application shell and persistence services are real. It
              does not pretend later Agent-building features are finished.
            </p>
          </div>
          <SystemStatus />
        </section>
      </main>

      <footer>
        <p>AgentSprout Studio · Independent interview concept</p>
        <p>Designed for supervised learning with ages 7–18.</p>
      </footer>
    </div>
  );
}
