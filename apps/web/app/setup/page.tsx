import Link from "next/link";
import { SetupForm } from "./setup-form";

export default function SetupPage() {
  return (
    <main>
      <Link className="back-link" href="/">
        ← Decision Center
      </Link>
      <section className="eyebrow">Phase 1 · Control context</section>
      <h1 className="setup-title">Establish the governed project boundary.</h1>
      <p className="lede">
        This development setup creates an organization and its first project. Authorized
        schedule, budget, and BOQ versions remain separate and require an explicit activation
        with an approval reference.
      </p>
      <SetupForm />
    </main>
  );
}

