"use client";

import { useEffect, useState } from "react";
import { currentIdentity, type Identity } from "./workspace-session";

const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";

export function SessionControl() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { void currentIdentity().then(setIdentity).catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Sign-in is unavailable.")); }, []);
  async function signOut() {
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/v1/auth/logout`, { method: "POST" });
      if (!response.ok) throw new Error("Sign-out failed. Please retry.");
      sessionStorage.clear();
      localStorage.removeItem("vai-project-workspace");
      localStorage.removeItem("vai-active-project");
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- Clear every in-memory project cache after sign-out.
      window.location.assign("/");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Sign-out failed."); setBusy(false); }
  }
  if (identity?.mode === "DEVELOPMENT") return <span className="session-control">Local evaluation</span>;
  return <div className="session-control">{identity?.mode === "OIDC" ? <><span>Signed in</span><button disabled={busy} onClick={() => void signOut()}>Sign out</button></> : <a href={`${API}/api/v1/auth/login`}>Sign in</a>}{message ? <span role="status">{message}</span> : null}</div>;
}
