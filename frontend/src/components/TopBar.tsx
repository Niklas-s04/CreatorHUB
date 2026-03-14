import { useEffect, useMemo, useState } from "react";
import { Link, NavLink as RouterNavLink, useLocation } from "react-router-dom";

type NavItem = { to: string; label: string };

const NAV_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/products", label: "Inventory" },
  { to: "/assets", label: "Assets" },
  { to: "/content", label: "Content" },
  { to: "/email", label: "Email" },
  { to: "/settings", label: "Settings" },
];

function NavLink({ to, label }: NavItem) {
  return (
    <RouterNavLink
      to={to}
      className={({ isActive }) => (isActive ? "active" : "")}
      end={to === "/dashboard"}
    >
      {label}
    </RouterNavLink>
  );
}

export default function TopBar() {
  const loc = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [loc.pathname]);

  const currentLabel = useMemo(() => {
    const found = NAV_ITEMS.find(item => loc.pathname === item.to || loc.pathname.startsWith(item.to + "/"));
    return found?.label ?? "CreatorHUB";
  }, [loc.pathname]);

  return (
    <div className="topbar">
      <div className="topbar-inner">
        <Link className="brand" to="/dashboard">CreatorHUB</Link>
        <div className="current-page">{currentLabel}</div>
        <div className="nav nav-main">
          {NAV_ITEMS.map(item => (
            <NavLink key={item.to} to={item.to} label={item.label} />
          ))}
        </div>
        <div className="nav nav-actions">
          <Link to="/products" className="btn primary small-btn">+ Produkt</Link>
          <Link to="/email" className="btn small-btn">E-Mail</Link>
        </div>
        <button
          type="button"
          className="menu-toggle"
          onClick={() => setMenuOpen(v => !v)}
          aria-expanded={menuOpen}
          aria-label="Navigation öffnen"
        >
          Menü
        </button>
      </div>
      <div className={menuOpen ? "mobile-menu open" : "mobile-menu"}>
        <div className="mobile-menu-inner">
          {NAV_ITEMS.map(item => (
            <NavLink key={`m-${item.to}`} to={item.to} label={item.label} />
          ))}
        </div>
      </div>
    </div>
  );
}