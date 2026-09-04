import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "VAI Decision Center",
  description: "Governed construction project-control decision intelligence",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

