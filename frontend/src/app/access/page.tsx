import Link from "next/link";
import { Suspense } from "react";

import { AccessForm } from "@/components/access-form";

export default function AccessPage() {
  return (
    <main className="access-page">
      <section className="access-intro" aria-labelledby="access-title">
        <Link className="wordmark" href="/" aria-label="AgentSprout Studio home">
          <span className="sprout-mark" aria-hidden="true">
            <i />
            <i />
          </span>
          AgentSprout
        </Link>
        <div>
          <p className="eyebrow">Protected concept studio</p>
          <h1 id="access-title">Open the workshop.</h1>
          <p>
            This shared code protects an interview demo; it is not a school account or identity
            system. Studio work is intended for supervised exploration.
          </p>
        </div>
        <p className="access-footnote">Independent product concept · No child profile required</p>
      </section>
      <Suspense fallback={<section className="access-panel" aria-busy="true">Opening access desk…</section>}>
        <AccessForm />
      </Suspense>
    </main>
  );
}
