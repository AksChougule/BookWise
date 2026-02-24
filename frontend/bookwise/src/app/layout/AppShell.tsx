import { Link, Outlet } from "react-router-dom";

import { AdminButton } from "../../components/AdminButton";
import { ThemeToggle } from "../../components/ThemeToggle";

export default function AppShell() {
  return (
    <div className="min-h-screen bg-app text-primary">
      <header className="sticky top-0 z-10 border-b border-app bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            BookWise
          </Link>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <AdminButton />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
