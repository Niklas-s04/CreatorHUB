import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import TopBar from "./components/TopBar";
import Sidebar from "./components/Sidebar";
import { checkSession } from "./api";
import { GlobalLoading } from "./shared/ui/states/GlobalLoading";
import { Breadcrumbs } from "./shared/ui/navigation/Breadcrumbs";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ProductsPage = lazy(() => import("./pages/ProductsPage"));
const ProductDetailPage = lazy(() => import("./pages/ProductDetailPage"));
const EmailPage = lazy(() => import("./pages/EmailPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const ContentPage = lazy(() => import("./pages/ContentPage"));
const AssetsPage = lazy(() => import("./pages/AssetsPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const AuditPage = lazy(() => import("./pages/AuditPage"));
const OperationsPage = lazy(() => import("./pages/OperationsPage"));

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
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!menuOpen) {
      previousFocusRef.current?.focus();
      return;
    }

    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const drawerEl = drawerRef.current;
    if (!drawerEl) return;

    const selector = [
      'button:not([disabled])',
      'a[href]',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(', ');

    const focusables = Array.from(drawerEl.querySelectorAll<HTMLElement>(selector));
    const firstFocusable = focusables[0] ?? drawerEl;
    firstFocusable.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setMenuOpen(false);
        return;
      }
      if (event.key !== 'Tab') return;

      const allFocusable = Array.from(drawerEl!.querySelectorAll<HTMLElement>(selector));
      if (!allFocusable.length) {
        event.preventDefault();
        drawerEl!.focus();
        return;
      }
      const first = allFocusable[0];
      const last = allFocusable[allFocusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);

  return (
    <div className="app-shell">
      <Sidebar />
      {menuOpen && <button type="button" className="sidebar-overlay" onClick={() => setMenuOpen(false)} aria-label="Menü schließen" />}
      <div
        id="mobile-navigation-drawer"
        className={menuOpen ? "sidebar-drawer open" : "sidebar-drawer"}
        role="dialog"
        aria-modal="true"
        aria-label="Seitennavigation"
        tabIndex={-1}
        ref={drawerRef}
      >
        <Sidebar onNavigate={() => setMenuOpen(false)} />
      </div>
      <div className="app-main">
        <TopBar menuOpen={menuOpen} onToggleMenu={() => setMenuOpen(v => !v)} />
        <main id="main-content" className="main-content" tabIndex={-1}>
          <Breadcrumbs />
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<GlobalLoading label="Seite wird geladen…" />}>
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
    </Suspense>
  );
}