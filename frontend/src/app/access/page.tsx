import Link from "next/link";
import { Suspense } from "react";

import { AccessForm } from "@/components/access-form";

export default function AccessPage() {
  return (
    <main className="access-page">
      <Suspense fallback={<section className="access-panel" aria-busy="true">Opening Studio…</section>}>
        <AccessForm />
      </Suspense>
      <section className="access-intro" aria-labelledby="access-title">
        <Link className="wordmark" href="/" aria-label="AgentSprout Studio home">
          <span className="sprout-mark" aria-hidden="true">
            <i />
            <i />
          </span>
          AgentSprout
        </Link>
        <div>
          <p className="eyebrow">Protected Studio</p>
          <h1 id="access-title">Build, test, and review learning Agents.</h1>
          <p>
            This shared code protects the product demo. No learner profile is created, and Studio
            work is intended for supervised exploration.
          </p>
        </div>
        <p className="access-footnote">Independent product concept · No child profile required</p>
      </section>
    </main>
  );
}
