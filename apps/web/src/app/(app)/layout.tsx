import { AppHeader } from "@/components/layout/AppHeader";

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen">
      <AppHeader />
      {children}
    </main>
  );
}
