const API = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
export type Workspace = { actorId: string; organizationId: string; organizationName?: string };
export type Identity = { mode: "DEVELOPMENT" | "OIDC"; actor_id: string | null; organization_id: string | null };
let pending: Promise<Identity> | undefined;
let validUntil = 0;

export async function currentIdentity(): Promise<Identity> {
  if (!pending || Date.now() >= validUntil) {
    validUntil = Date.now() + 10_000;
    pending = fetch(`${API}/api/v1/auth/session`, { cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error(response.status === 401 ? "Sign in to open your project workspace." : "Identity service is unavailable.");
      return await response.json() as Identity;
    }).catch((error: unknown) => { pending = undefined; throw error; });
  }
  return pending;
}

export async function currentWorkspace(): Promise<Workspace | null> {
  const identity = await currentIdentity();
  if (identity.mode === "OIDC") {
    if (!identity.actor_id || !identity.organization_id) throw new Error("Signed-in project identity is unavailable.");
    return { actorId: identity.actor_id, organizationId: identity.organization_id };
  }
  const saved = localStorage.getItem("vai-project-workspace") ?? sessionStorage.getItem("vai-project-workspace");
  if (!saved) return null;
  try { return JSON.parse(saved) as Workspace; }
  catch { localStorage.removeItem("vai-project-workspace"); sessionStorage.removeItem("vai-project-workspace"); return null; }
}
