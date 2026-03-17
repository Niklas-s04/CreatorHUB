import { NavLink } from "react-router-dom";
import { logout } from "../api";

type NavItem = {
  to: string;
  label: string;
  icon: string;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Hauptmenü",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: "◧" },
      { to: "/products", label: "Produkte", icon: "◫" },
      { to: "/assets", label: "Assets", icon: "◩" },
    ],
  },
  {
    title: "Inhalte",
    items: [
      { to: "/content", label: "Content", icon: "✎" },
      { to: "/email", label: "E-Mail", icon: "✉" },
    ],
  },
  {
    title: "System",
    items: [
      { to: "/settings", label: "Einstellungen", icon: "⚙" },
      { to: "/admin", label: "Admin", icon: "⌘" },
    ],
  },
];

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  async function onLogout() {
    await logout();
    window.location.href = "/login";
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">CreatorHUB</div>
      <div className="sidebar-nav">
        {NAV_SECTIONS.map(section => (
          <div className="sidebar-section" key={section.title}>
            <div className="sidebar-section-title">{section.title}</div>
            {section.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/dashboard"}
                className={({ isActive }) => (isActive ? "sidebar-link active" : "sidebar-link")}
                onClick={onNavigate}
              >
                <span className="sidebar-icon" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </div>
      <button type="button" className="sidebar-logout" onClick={onLogout}>
        <span className="sidebar-icon" aria-hidden="true">⇥</span>
        <span>Logout</span>
      </button>
    </aside>
  );
}
