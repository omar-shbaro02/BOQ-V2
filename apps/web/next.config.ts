import type { NextConfig } from "next";

const upstream = process.env.VAI_API_INTERNAL_URL;
if (upstream) {
  const parsed = new URL(upstream);
  if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password || parsed.pathname !== "/" || parsed.search || parsed.hash) throw new Error("VAI_API_INTERNAL_URL must be a trusted API origin");
  if (process.env.NEXT_PUBLIC_VAI_API_URL !== "") throw new Error("Proxied browser sessions require NEXT_PUBLIC_VAI_API_URL to be empty");
}
const production = process.env.NODE_ENV === "production";
const proxyMaxBytes = Number(process.env.VAI_MAX_REQUEST_BYTES ?? 64 * 1024 * 1024);
if (!Number.isSafeInteger(proxyMaxBytes) || proxyMaxBytes < 1024 || proxyMaxBytes > 128 * 1024 * 1024) throw new Error("VAI_MAX_REQUEST_BYTES must be between 1 KiB and 128 MiB");
const apiUrl = process.env.NEXT_PUBLIC_VAI_API_URL ?? "http://localhost:8000";
const apiOrigin = apiUrl ? new URL(apiUrl).origin : "";
const csp = `default-src 'self'; script-src 'self' 'unsafe-inline'${production ? "" : " 'unsafe-eval'"}; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ${apiOrigin}${production ? "" : " ws: wss:"}; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'`;

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: { proxyClientMaxBodySize: proxyMaxBytes },
  async rewrites() { return upstream ? [{ source: "/api/v1/:path*", destination: `${upstream.replace(/\/$/, "")}/api/v1/:path*` }] : []; },
  async headers() { return [{ source: "/:path*", headers: [
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "no-referrer" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    { key: "Content-Security-Policy", value: csp },
    ...(production && process.env.VAI_SESSION_PUBLIC_ORIGIN?.startsWith("https://") ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }] : []),
  ] }]; },
};

export default nextConfig;

