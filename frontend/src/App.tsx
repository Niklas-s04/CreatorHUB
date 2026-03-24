import { useEffect, useState } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import TopBar from "./components/TopBar";
import Sidebar from "./components/Sidebar";
import DashboardPage from "./pages/DashboardPage";
import ProductsPage from "./pages/ProductsPage";
import ProductDetailPage from "./pages/ProductDetailPage";
import EmailPage from "./pages/EmailPage";
import SettingsPage from "./pages/SettingsPage";
import ContentPage from "./pages/ContentPage";
import AssetsPage from "./pages/AssetsPage";
import LoginPage from "./pages/LoginPage";
import { checkSession } from "./api";
import AdminPage from "./pages/AdminPage";
import AuditPage from "./pages/AuditPage";
import OperationsPage from "./pages/OperationsPage";
import { GlobalLoading } from "./shared/ui/states/GlobalLoading";
import { Breadcrumbs } from "./shared/ui/navigation/Breadcrumbs";

function RequireAuth() {
  const [state, setState] = useState<"loading" | "ok" | "no">("loading");

  useEffect(() => {
    let mounted = true;
    checkSession().then(ok => {
      if (mounted) setState(ok ? "ok" : "no");
    });
    return () => {
      mounted = false;
    };
  }, []);

  if (state === "loading") return <GlobalLoading label="Session wird geprüft…" />;
  if (state === "no") return <Navigate to="/login" replace />;
  return <Outlet />;
}

function PublicOnly() {
  const [state, setState] = useState<"loading" | "authed" | "guest">("loading");

  useEffect(() => {
    let mounted = true;
    checkSession().then(ok => {
      if (mounted) setState(ok ? "authed" : "guest");
    });
    return () => {
      mounted = false;
    };
  }, []);

  if (state === "loading") return <GlobalLoading label="Session wird geprüft…" />;
  if (state === "authed") return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar />
      {menuOpen && <button className="sidebar-overlay" onClick={() => setMenuOpen(false)} aria-label="Menü schließen" />}
      <div className={menuOpen ? "sidebar-drawer open" : "sidebar-drawer"}>
        <Sidebar onNavigate={() => setMenuOpen(false)} />
      </div>
      <div className="app-main">
        <TopBar onToggleMenu={() => setMenuOpen(v => !v)} />
        <main className="main-content">
          <Breadcrumbs />
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnly />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/operations" element={<OperationsPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/products/:id" element={<ProductDetailPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/content" element={<ContentPage />} />
          <Route path="/email" element={<EmailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}