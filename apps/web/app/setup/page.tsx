import { SetupForm } from "./setup-form";

export default function SetupPage() {
  return (
    <main className="project-setup-page">
      <section className="eyebrow">Project workspace</section>
      <h1 className="setup-title">Set up your project.</h1>
      <p className="lede">Create a project, then define its work packages, charter and report recipients. Review and authorization remain separate from reported project updates.</p>
      <SetupForm />
    </main>
  );
}

