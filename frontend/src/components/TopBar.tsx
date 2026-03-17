export default function TopBar({ onToggleMenu }: { onToggleMenu: () => void }) {
  return (
    <div className="topbar">
      <div className="topbar-inner">
        <button className="topbar-menu-btn" onClick={onToggleMenu} aria-label="Navigation öffnen">☰</button>
        <div className="topbar-search-wrap">
          <input className="topbar-search" placeholder="Suchen …" aria-label="Suchen" />
        </div>
        <div className="topbar-right">
          <div className="topbar-icon-btn" aria-label="Benachrichtigungen">
            🔔
            <span className="badge">3</span>
          </div>
          <div className="topbar-icon-btn" aria-label="Nachrichten">
            ✉
            <span className="badge">7</span>
          </div>
          <div className="topbar-profile" aria-label="Profil">NH</div>
        </div>
      </div>
    </div>
  );
}