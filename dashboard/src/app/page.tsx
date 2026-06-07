import { ApiConnectionBadge } from "@/components/ApiConnectionBadge";
import { DashboardShell } from "@/components/DashboardShell";

export default function HomePage() {
  return (
    <>
      <DashboardShell />
      <ApiConnectionBadge />
    </>
  );
}
