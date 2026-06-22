// src/pages/DevicesPage.tsx
// Manage farms and devices; show watering log history.
import { useEffect, useState } from 'react';
import { farmsApi, devicesApi, wateringApi, predictionsApi } from '../api/client';
import type { Farm, Device, WateringLog } from '../api/client';

function fmtDuration(s: number) {
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function DevicesPage() {
  const [farms, setFarms]         = useState<Farm[]>([]);
  const [devices, setDevices]     = useState<Device[]>([]);
  const [logs, setLogs]           = useState<WateringLog[]>([]);
  const [selFarm, setSelFarm]     = useState<number | null>(null);
  const [selDevice, setSelDevice] = useState<number | null>(null);
  const [training, setTraining]   = useState(false);
  const [trainMsg, setTrainMsg]   = useState('');

  useEffect(() => {
    farmsApi.list().then(fs => {
      setFarms(fs);
      if (fs.length > 0) setSelFarm(fs[0].id);
    });
  }, []);

  useEffect(() => {
    if (!selFarm) return;
    devicesApi.list(selFarm).then(ds => {
      setDevices(ds);
      if (ds.length > 0) setSelDevice(ds[0].id);
    });
  }, [selFarm]);

  useEffect(() => {
    if (!selDevice) return;
    wateringApi.logs(selDevice, 30).then(setLogs);
  }, [selDevice]);

  async function trainModel() {
    setTraining(true); setTrainMsg('');
    try {
      const r = await predictionsApi.train();
      setTrainMsg(r.message);
    } catch (e) {
      setTrainMsg('Training failed.');
    } finally { setTraining(false); }
  }

  return (
    <div className="animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">DEVICES & FARMS</h1>
          <p className="page-subtitle">Manage nodes, view watering history, retrain ML model</p>
        </div>
        <button
          id="train-model-btn"
          className="btn btn-orange"
          onClick={trainModel}
          disabled={training}
        >
          {training ? '[ TRAINING… ]' : '[ ⚙ RETRAIN ML ]'}
        </button>
      </div>

      {trainMsg && (
        <div style={{ padding: '0.75rem 1rem', border: '2px solid #39ff14', color: '#39ff14', fontSize: '0.78rem', marginBottom: '1.5rem' }}>
          ✓ {trainMsg}
        </div>
      )}

      {/* Farms table */}
      <div className="card mb-4">
        <div className="card-header">
          <span className="card-title">Registered Farms</span>
          <span className="badge badge-green">{farms.length}</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th><th>Name</th><th>Location</th><th>Created</th>
            </tr>
          </thead>
          <tbody>
            {farms.length === 0 && (
              <tr><td colSpan={4} className="text-muted text-sm">No farms registered.</td></tr>
            )}
            {farms.map(f => (
              <tr key={f.id}>
                <td className="text-muted">#{f.id}</td>
                <td><strong>{f.name}</strong></td>
                <td className="text-muted">{f.location}</td>
                <td className="text-muted text-xs">{new Date(f.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Devices table */}
      <div className="card mb-4">
        <div className="card-header">
          <span className="card-title">Sensor Nodes</span>
          <div className="flex gap-1">
            <select
              id="devices-farm-select"
              className="input-field"
              style={{ padding: '0.3rem 0.6rem', width: 'auto', fontSize: '0.75rem' }}
              value={selFarm ?? ''}
              onChange={e => setSelFarm(Number(e.target.value))}
            >
              {farms.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
            <span className="badge badge-green">{devices.length}</span>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr><th>ID</th><th>Name</th><th>API Key</th><th>Status</th><th>Created</th></tr>
          </thead>
          <tbody>
            {devices.length === 0 && (
              <tr><td colSpan={5} className="text-muted text-sm">No devices in this farm.</td></tr>
            )}
            {devices.map(d => (
              <tr key={d.id}>
                <td className="text-muted">#{d.id}</td>
                <td><strong>{d.name}</strong></td>
                <td><code className="text-green text-xs">{d.api_key}</code></td>
                <td><span className={`badge badge-${d.status === 'active' ? 'green' : 'gray'}`}>{d.status}</span></td>
                <td className="text-muted text-xs">{new Date(d.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Watering log */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Watering History</span>
          <div className="flex gap-1" style={{ alignItems: 'center' }}>
            <select
              id="log-device-select"
              className="input-field"
              style={{ padding: '0.3rem 0.6rem', width: 'auto', fontSize: '0.75rem' }}
              value={selDevice ?? ''}
              onChange={e => {
                setSelDevice(Number(e.target.value));
                wateringApi.logs(Number(e.target.value), 30).then(setLogs);
              }}
            >
              {devices.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <span className="badge badge-green">{logs.length} events</span>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr><th>Time</th><th>Duration</th><th>Trigger</th><th>Status</th></tr>
          </thead>
          <tbody>
            {logs.length === 0 && (
              <tr><td colSpan={4} className="text-muted text-sm">No watering events logged yet.</td></tr>
            )}
            {[...logs].reverse().map(l => (
              <tr key={l.id}>
                <td className="text-muted text-xs">{new Date(l.timestamp).toLocaleString()}</td>
                <td><strong className="text-green">{fmtDuration(l.duration_seconds)}</strong></td>
                <td>
                  <span className={`badge ${l.manual_override ? 'badge-orange' : 'badge-green'}`}>
                    {l.manual_override ? 'MANUAL' : 'AUTO'}
                  </span>
                </td>
                <td><span className={`badge badge-${l.status === 'completed' ? 'green' : 'gray'}`}>{l.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
