// src/App.tsx — Root component with auth guard, nav shell, and page routing.
import { useEffect, useState } from 'react';
import './index.css';
import { authApi, farmsApi } from './api/client';
import AuthPage      from './pages/AuthPage';
import SetupPage     from './pages/SetupPage';
import DashboardPage from './pages/DashboardPage';
import DevicesPage   from './pages/DevicesPage';

type Page = 'dashboard' | 'devices';

export default function App() {
  const [authed, setAuthed]     = useState(false);
  const [needSetup, setNeedSetup] = useState(false);
  const [page, setPage]         = useState<Page>('dashboard');
  const [username, setUsername] = useState('');
  const [checking, setChecking] = useState(true);

  // Validate stored token on mount
  useEffect(() => {
    const token = localStorage.getItem('agri_token');
    if (!token) { setChecking(false); return; }
    authApi.me()
      .then(user => {
        setUsername(user.username);
        setAuthed(true);
        return farmsApi.list();
      })
      .then(farms => { setNeedSetup(farms.length === 0); })
      .catch(() => { localStorage.removeItem('agri_token'); })
      .finally(() => setChecking(false));
  }, []);

  function handleLogin() {
    authApi.me().then(user => {
      setUsername(user.username);
      setAuthed(true);
      farmsApi.list().then(farms => setNeedSetup(farms.length === 0));
    });
  }

  function handleLogout() {
    localStorage.removeItem('agri_token');
    setAuthed(false);
    setNeedSetup(false);
    setUsername('');
  }

  function handleSetupComplete() { setNeedSetup(false); }

  // ── Loading splash ──────────────────────────────────────────────
  if (checking) {
    return (
      <div className="flex-center" style={{ height: '100vh', flexDirection: 'column', gap: '1rem' }}>
        <div className="pulse-dot" style={{ width: 16, height: 16 }} />
        <p className="text-muted text-xs upper">Initialising system…</p>
      </div>
    );
  }

  // ── Auth gate ──────────────────────────────────────────────────
  if (!authed) return <AuthPage onLogin={handleLogin} />;

  // ── First-time setup ───────────────────────────────────────────
  if (needSetup) return <SetupPage onComplete={handleSetupComplete} />;

  // ── Main shell ─────────────────────────────────────────────────
  return (
    <div className="app-shell">
      {/* Topbar */}
      <header className="topbar">
        <span className="topbar-logo">Agri<span>Monitor</span></span>
        <span className="text-muted text-xs" style={{ marginLeft: '1rem' }}>
          PRECISION IRRIGATION SYSTEM
        </span>
        <div className="topbar-right">
          <span className="pulse-dot" />
          <span className="text-xs text-muted upper">LIVE</span>
          <span className="text-xs text-muted">|</span>
          <span className="text-xs upper text-green">{username}</span>
          <button
            id="logout-btn"
            className="btn btn-sm"
            onClick={handleLogout}
          >Logout</button>
        </div>
      </header>

      <div className="app-main">
        {/* Sidebar */}
        <nav className="sidebar">
          <p className="nav-section-label">Navigation</p>

          <div
            id="nav-dashboard"
            className={`nav-item ${page === 'dashboard' ? 'active' : ''}`}
            onClick={() => setPage('dashboard')}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && setPage('dashboard')}
          >
            <span className="nav-icon">◈</span>
            Live Monitor
          </div>

          <div
            id="nav-devices"
            className={`nav-item ${page === 'devices' ? 'active' : ''}`}
            onClick={() => setPage('devices')}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && setPage('devices')}
          >
            <span className="nav-icon">◉</span>
            Devices &amp; Farms
          </div>

          {/* System status block at bottom of sidebar */}
          <div style={{ marginTop: 'auto', padding: '1.5rem', borderTop: '1px solid #1a1a1a' }}>
            <p className="text-xs upper text-muted mb-1">System</p>
            <div className="flex gap-1" style={{ alignItems: 'center', marginBottom: '0.5rem' }}>
              <span className="pulse-dot" />
              <span className="text-xs text-green">Backend Online</span>
            </div>
            <p className="text-xs text-muted">ESP32 Edge Filter</p>
            <p className="text-xs text-green">Moving Avg ×10</p>
            <p className="text-xs text-muted mt-1">ML Engine</p>
            <p className="text-xs text-green">Random Forest</p>
          </div>
        </nav>

        {/* Content */}
        <main className="content-area">
          {page === 'dashboard' && <DashboardPage />}
          {page === 'devices'   && <DevicesPage />}
        </main>
      </div>
    </div>
  );
}
