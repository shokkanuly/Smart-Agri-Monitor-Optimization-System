// src/pages/AuthPage.tsx
import { useState } from 'react';
import type { FormEvent } from 'react';
import { authApi } from '../api/client';

interface Props { onLogin: () => void; }

export default function AuthPage({ onLogin }: Props) {
  const [mode, setMode]         = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      if (mode === 'register') {
        await authApi.register(username, password);
        setMode('login');
        setError('');
        return;
      }
      const token = await authApi.login(username, password);
      localStorage.setItem('agri_token', token.access_token);
      onLogin();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      {/* ── Left panel: hero copy ── */}
      <div className="auth-panel auth-panel-left">
        <p className="auth-hero-tag">▶ Turkey Agri-Tech Initiative 2026</p>
        <h1 className="auth-hero-title">
          Smart<br />
          <span className="accent">Agri-Monitor</span><br />
          & Optimizer
        </h1>
        <p className="auth-hero-desc">
          IoT-based precision irrigation &amp; soil health monitoring.
          ESP32 edge nodes stream live telemetry. Our ML engine schedules
          optimal watering to minimize water consumption by up to&nbsp;25%.
        </p>
        <div className="auth-stat-row">
          <div className="auth-stat">
            <div className="stat-val">25%</div>
            <div className="stat-lbl">Water Saved</div>
          </div>
          <div className="auth-stat">
            <div className="stat-val">3</div>
            <div className="stat-lbl">Sensor Types</div>
          </div>
          <div className="auth-stat">
            <div className="stat-val">ML</div>
            <div className="stat-lbl">Predictions</div>
          </div>
        </div>
      </div>

      {/* ── Right panel: form ── */}
      <div className="auth-panel" style={{ maxWidth: 480, margin: '0 auto' }}>
        <p className="text-muted text-xs upper mb-2">
          <span className="pulse-dot" style={{ marginRight: 6 }} />
          System Online
        </p>
        <h2 className="auth-form-title">
          {mode === 'login' ? 'Access Dashboard' : 'Create Account'}
        </h2>
        <p className="auth-form-sub">
          {mode === 'login'
            ? 'Enter credentials to access your farm network.'
            : 'Register a new operator account.'}
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="username">Username</label>
            <input
              id="username"
              className="input-field"
              type="text"
              placeholder="operator_01"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoComplete="username"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="input-field"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div style={{
              padding: '0.75rem 1rem',
              border: '2px solid #ff2d2d',
              color: '#ff2d2d',
              fontSize: '0.78rem',
              marginBottom: '1rem',
              fontFamily: 'var(--mono)',
            }}>
              ⚠ {error}
            </div>
          )}

          <button
            id="auth-submit-btn"
            type="submit"
            className="btn btn-green w-full btn-lg"
            style={{ justifyContent: 'center' }}
            disabled={loading}
          >
            {loading ? '[ LOADING… ]' : mode === 'login' ? '[ LOGIN ]' : '[ CREATE ACCOUNT ]'}
          </button>
        </form>

        <p style={{ marginTop: '1.5rem', fontSize: '0.78rem', color: '#555', textAlign: 'center' }}>
          {mode === 'login' ? "No account? " : "Have an account? "}
          <button
            className="text-green"
            style={{ background: 'none', border: 'none', cursor: 'pointer', font: 'inherit' }}
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
          >
            {mode === 'login' ? 'Register →' : '← Back to Login'}
          </button>
        </p>

        <p style={{ marginTop: '3rem', fontSize: '0.65rem', color: '#333', textAlign: 'center' }}>
          SMART AGRI-MONITOR v1.0 · PRECISION IRRIGATION SYSTEM
        </p>
      </div>
    </div>
  );
}
