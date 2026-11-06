import { CostWorkbench } from "./cost-workbench";

export default function CostPage() {
  return <main className="workbench-shell approved-schedule-page">
    <header className="as-heading"><span className="eyebrow">Project spending</span><h1>Cost control</h1><p>Record costs from your evidence and review the saved records against the approved budget.</p></header>
    <CostWorkbench />
  </main>;
}
