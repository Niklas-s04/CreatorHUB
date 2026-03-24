import { NavLink } from "react-router-dom";
import { logout } from "../../../api";
import { useAuthz } from "../../hooks/useAuthz";
import { NAV_SECTIONS_TASK_BASED } from "../../navigation/navConfig";

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { hasPermission } = useAuthz();

  async function onLogout() {
    await logout();
    window.location.href = "/login";
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">CreatorHUB</div>
      <div className="sidebar-nav">
        {NAV_SECTIONS_TASK_BASED.map(section => (
          <div className="sidebar-section" key={section.title}>
            <div className="sidebar-section-title">{section.title}</div>
            {section.items
              .filter(item => !item.requiredPermission || hasPermission(item.requiredPermission))
              .map(item => (
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
