import { Link, useLocation } from "react-router-dom";

export function AdminButton() {
  const location = useLocation();
  const isActive = location.pathname.startsWith("/admin");

  return (
    <Link
      to="/admin"
      className={`rounded-md border px-3 py-1.5 text-sm transition focus-visible:ring ${
        isActive
          ? "border-app bg-primary text-surface"
          : "border-app bg-surface text-primary hover:bg-muted"
      }`}
      aria-label="Open admin panel"
    >
      Admin
    </Link>
  );
}
