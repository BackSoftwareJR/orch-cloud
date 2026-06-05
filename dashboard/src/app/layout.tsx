import type { Metadata } from "next";

import { DashboardShell } from "@/components/DashboardShell";

import "./globals.css";

export const metadata: Metadata = {
  title: "HyperOrchestrator Dashboard",
  description: "H24 multi-project orchestration platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
