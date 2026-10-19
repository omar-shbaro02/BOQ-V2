import { SetupForm } from "./setup-form";

export default function SetupPage() {
  return (
    <main className="project-setup-page">
      <section className="eyebrow">Project workspace</section>
      <h1 className="setup-title">Create a project.</h1>
      <p className="lede">Add the basic project details once. Internal workspace identifiers are managed automatically in this local evaluation build.</p>
      <SetupForm />
    </main>
  );
}

