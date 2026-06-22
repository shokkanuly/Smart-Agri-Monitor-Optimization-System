// src/pages/SetupPage.tsx
// Farm + Device registration wizard shown when no farms exist yet.
import { useState } from 'react';
import type { FormEvent } from 'react';
import { farmsApi, devicesApi } from '../api/client';
import type { Farm, Device } from '../api/client';

interface Props { onComplete: () => void; }

export default function SetupPage({ onComplete }: Props) {
  const [step, setStep]           = useState<1 | 2>(1);
  const [farmName, setFarmName]   = useState('');
  const [location, setLocation]   = useState('Izmir, Turkey');
  const [farm, setFarm]           = useState<Farm | null>(null);
  const [deviceName, setDeviceName] = useState('');
  const [devices, setDevices]     = useState<Device[]>([]);
  const [error, setError]         = useState('');
  const [loading, setLoading]     = useState(false);

  async function createFarm(e: FormEvent) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const f = await farmsApi.create(farmName, location);
      setFarm(f);
      setStep(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally { setLoading(false); }
  }

  async function addDevice(e: FormEvent) {
    e.preventDefault();
    if (!farm) return;
    setError(''); setLoading(true);
    try {
      const d = await devicesApi.create(deviceName, farm.id);
      setDevices(prev => [...prev, d]);
      setDeviceName('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally { setLoading(false); }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
      <div style={{ width: '100%', maxWidth: 520 }}>
        <p className="text-xs upper text-muted mb-2">
          ◈ First-Time Setup — Step {step}/2
        </p>
        <h1 style={{ fontSize: '2rem', fontFamily: 'var(--sans)', marginBottom: '2rem' }}>
          {step === 1 ? 'Register Your Farm' : 'Add Sensor Nodes'}
        </h1>

        {step === 1 && (
          <form onSubmit={createFarm}>
            <div className="form-group">
              <label className="form-label">Farm Name</label>
              <input className="input-field" placeholder="Anatolian Olive Grove" value={farmName}
                onChange={e => setFarmName(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Location</label>
              <input className="input-field" placeholder="Izmir, Turkey" value={location}
                onChange={e => setLocation(e.target.value)} />
            </div>
            {error && <p className="text-red text-sm mb-2">⚠ {error}</p>}
            <button type="submit" className="btn btn-green btn-lg w-full" style={{ justifyContent: 'center' }} disabled={loading}>
              {loading ? '[ CREATING… ]' : '[ CREATE FARM → ]'}
            </button>
          </form>
        )}

        {step === 2 && (
          <div>
            <div className="card card-green mb-3">
              <div className="card-header">
                <span className="card-title">Farm Created</span>
                <span className="badge badge-green">Active</span>
              </div>
              <p className="text-sm"><span className="text-muted">Name:</span> {farm?.name}</p>
              <p className="text-sm mt-1"><span className="text-muted">Location:</span> {farm?.location}</p>
            </div>

            <form onSubmit={addDevice} style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
              <input className="input-field" placeholder="Node-A (Wheat Sector)" value={deviceName}
                onChange={e => setDeviceName(e.target.value)} required style={{ flex: 1 }} />
              <button type="submit" className="btn btn-green" disabled={loading}>
                {loading ? '…' : '[ + ADD ]'}
              </button>
            </form>

            {error && <p className="text-red text-sm mb-2">⚠ {error}</p>}

            {devices.length > 0 && (
              <div className="card mb-3">
                <div className="card-header">
                  <span className="card-title">Registered Nodes</span>
                  <span className="badge badge-green">{devices.length}</span>
                </div>
                {devices.map(d => (
                  <div key={d.id} style={{ padding: '0.6rem 0', borderBottom: '1px solid #1c1c1c' }}>
                    <p className="text-sm">{d.name}</p>
                    <p className="text-xs text-muted mono" style={{ marginTop: '0.2rem' }}>
                      API Key: <span className="text-green">{d.api_key}</span>
                    </p>
                    <p className="text-xs text-muted" style={{ marginTop: '0.1rem' }}>
                      Copy this key into simulator.py DEVICE_NODES
                    </p>
                  </div>
                ))}
              </div>
            )}

            {devices.length > 0 && (
              <button className="btn btn-green btn-lg w-full" style={{ justifyContent: 'center' }} onClick={onComplete}>
                [ GO TO DASHBOARD → ]
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
