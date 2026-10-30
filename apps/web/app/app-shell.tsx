"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { SessionControl } from "./session-control";
import { WorkflowNavigation, workflowGroups } from "./workflow-navigation";

const groups = [{ label: "Workspace overview", links: [{ href: "/", label: "Command center", icon: "grid" }] }, ...workflowGroups];

function subscribeToViewport(callback: () => void) {
  const query = window.matchMedia("(max-width: 850px)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const mobile = useSyncExternalStore(subscribeToViewport, () => window.matchMedia("(max-width: 850px)").matches, () => false);
  const navigationOpen = mobile && open;
  const sidebar = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!navigationOpen) return;
    const navigation = sidebar.current;
    const opener = menuButton.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    navigation?.querySelector<HTMLButtonElement>(".sidebar-close")?.focus();
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
      } else if (event.key === "Tab") {
        const controls = Array.from(navigation?.querySelectorAll<HTMLElement>("a[href], button:not(:disabled)") ?? []).filter((element) => element.getClientRects().length > 0);
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKey);
      opener?.focus();
    };
  }, [navigationOpen]);
  return <div className="app-frame">
    <a className="skip-link" href="#main-content" inert={navigationOpen}>Skip to main content</a>
    <aside ref={sidebar} id="primary-navigation" className={`app-sidebar ${navigationOpen ? "open" : ""}`} role={navigationOpen ? "dialog" : undefined} aria-modal={navigationOpen || undefined} aria-label="Primary navigation">
      <div className="brand-row"><Link className="brand" href="/" aria-label="VAI command center" onClick={() => setOpen(false)}><span className="brand-logo"><Image src="/vai-logo.png" alt="VAI" width={1920} height={1080} unoptimized preload /></span></Link><button className="sidebar-close" onClick={() => setOpen(false)} aria-label="Close navigation">×</button></div>
      <nav className="sidebar-nav" aria-label="Project workflow">{groups.map((group) => <div className="nav-group" key={group.label}><span className="nav-label">{group.label}</span>{group.links.map((link) => { const active = link.href === "/" ? pathname === "/" : (pathname === link.href || pathname.startsWith(`${link.href}/`)); return <Link className={`nav-link ${active ? "active" : ""}`} href={link.href} key={link.href} onClick={() => setOpen(false)} aria-current={active ? "page" : undefined}><NavIcon name={link.icon}/><span>{link.label}</span></Link>; })}</div>)}</nav>
      <div className="sidebar-project"><span className="project-avatar">PW</span><span><strong>Project workspace</strong><small>Follow the stages above</small></span></div>
    </aside>
    {navigationOpen ? <button className="sidebar-scrim" tabIndex={-1} aria-hidden="true" onClick={() => setOpen(false)}/> : null}
    <div className="app-stage" inert={navigationOpen}><header className="app-topbar"><button ref={menuButton} className="menu-button" onClick={() => setOpen(true)} aria-label="Open navigation" aria-controls="primary-navigation" aria-expanded={navigationOpen}><NavIcon name="menu"/></button><div className="topbar-context">Project control workspace <small>Plan · Evidence · Decisions</small></div><div className="topbar-actions"><Link className="topbar-queue" href="/decision-center">Decision queue <span aria-hidden="true">↗</span></Link><SessionControl /></div></header><div className="app-content" id="main-content" tabIndex={-1}>{pathname !== "/" ? <WorkflowNavigation pathname={pathname} position="top"/> : null}{children}{pathname !== "/" ? <WorkflowNavigation pathname={pathname} position="bottom"/> : null}</div></div>
  </div>;
}

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>, pulse: <><path d="M3 12h4l2-5 4 10 2-5h6"/><path d="M4 4h16v16H4z"/></>, folder: <path d="M3 6h7l2 2h9v11H3z"/>, layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>, trend: <><path d="M4 19V5M4 19h16"/><path d="m7 15 4-4 3 2 5-6"/></>, calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>, wallet: <><path d="M4 6h14a2 2 0 0 1 2 2v11H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h12"/><path d="M15 11h7v5h-7a2 2 0 0 1 0-5Z"/></>, chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>, file: <><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/></>, signal: <><path d="M5 19v-3M10 19v-7M15 19V8M20 19V4"/></>, briefcase: <><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V4h6v3M3 12h18M10 12v2h4v-2"/></>, target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>, nodes: <><circle cx="5" cy="12" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="m7 11 10-5M7 13l10 5"/></>, search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>, bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>, menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
  };
  return <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
