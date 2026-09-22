"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

const groups = [
  { label: "Overview", links: [{ href: "/", label: "Command center", icon: "grid" }, { href: "/decision-center", label: "Decision queue", icon: "pulse" }] },
  { label: "Plan & control", links: [{ href: "/bootstrap", label: "BOQ to schedule", icon: "layers" }, { href: "/progress", label: "Progress", icon: "trend" }, { href: "/schedule", label: "Schedule", icon: "calendar" }, { href: "/cost", label: "Cost control", icon: "wallet" }, { href: "/forecast", label: "Forecasts", icon: "chart" }] },
  { label: "Intelligence", links: [{ href: "/evidence", label: "Evidence", icon: "file" }, { href: "/signals", label: "Signals", icon: "signal" }, { href: "/cases", label: "Decision cases", icon: "briefcase" }, { href: "/impact", label: "Impact & priority", icon: "target" }, { href: "/orchestration", label: "Orchestration", icon: "nodes" }] },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  return <div className="app-frame">
    <aside className={`app-sidebar ${open ? "open" : ""}`} aria-label="Primary navigation">
      <div className="brand-row"><Link className="brand" href="/" onClick={() => setOpen(false)} aria-label="VAI command center"><span className="brand-mark">V</span><span><strong>VAI</strong><small>Project intelligence</small></span></Link><button className="sidebar-close" onClick={() => setOpen(false)} aria-label="Close navigation">×</button></div>
      <nav className="sidebar-nav">{groups.map((group) => <div className="nav-group" key={group.label}><span className="nav-label">{group.label}</span>{group.links.map((link) => { const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href); return <Link className={`nav-link ${active ? "active" : ""}`} href={link.href} key={link.href} onClick={() => setOpen(false)} aria-current={active ? "page" : undefined}><NavIcon name={link.icon}/><span>{link.label}</span>{link.href === "/signals" ? <i>5</i> : null}</Link>; })}</div>)}</nav>
      <div className="sidebar-project"><span className="project-avatar">PW</span><span><strong>Project workspace</strong><small>Connect in each workbench</small></span><span className="project-dot" aria-label="Workspace available"/></div>
    </aside>
    {open ? <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setOpen(false)}/> : null}
    <div className="app-stage"><header className="app-topbar"><button className="menu-button" onClick={() => setOpen(true)} aria-label="Open navigation"><NavIcon name="menu"/></button><div className="topbar-context"><span className="live-dot"/> Project control workspace <small>Governed decision intelligence</small></div><div className="topbar-actions"><button aria-label="Search"><NavIcon name="search"/></button><button className="notification-button" aria-label="Notifications"><NavIcon name="bell"/><i/></button><Link className="user-chip" href="/setup"><span>OA</span><span><strong>Local admin</strong><small>Configure project</small></span></Link></div></header><div className="app-content">{children}</div></div>
  </div>;
}

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>, pulse: <><path d="M3 12h4l2-5 4 10 2-5h6"/><path d="M4 4h16v16H4z"/></>, layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>, trend: <><path d="M4 19V5M4 19h16"/><path d="m7 15 4-4 3 2 5-6"/></>, calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>, wallet: <><path d="M4 6h14a2 2 0 0 1 2 2v11H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h12"/><path d="M15 11h7v5h-7a2 2 0 0 1 0-5Z"/></>, chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>, file: <><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/></>, signal: <><path d="M5 19v-3M10 19v-7M15 19V8M20 19V4"/></>, briefcase: <><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V4h6v3M3 12h18M10 12v2h4v-2"/></>, target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>, nodes: <><circle cx="5" cy="12" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="m7 11 10-5M7 13l10 5"/></>, search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>, bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>, menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
  };
  return <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
