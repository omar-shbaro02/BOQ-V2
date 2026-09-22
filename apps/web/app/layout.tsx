import type { Metadata } from "next";
import { Suspense } from "react";
import "./styles.css";
import { AppShell } from "./app-shell";

export const metadata: Metadata = {
  title: "VAI Decision Center",
  description: "Governed construction project-control decision intelligence",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><Suspense fallback={<div className="app-loading">Loading workspace…</div>}><AppShell>{children}</AppShell></Suspense></body>
    </html>
  );
}
