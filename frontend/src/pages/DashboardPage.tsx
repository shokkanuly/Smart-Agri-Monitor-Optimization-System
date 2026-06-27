// src/pages/DashboardPage.tsx
// Central monitoring view: live metrics, sparkline charts, anomaly feed,
// weather widget, ML prediction panel, and manual watering trigger.

import { useCallback, useEffect, useRef, useState } from 'react';
import LineChart from '../components/LineChart';
import {
  telemetryApi, weatherApi, predictionsApi, wateringApi,
  devicesApi, farmsApi, aiApi,
} from '../api/client';
import type { Farm, Device, Telemetry, Weather, Prediction, AiAdvice } from '../api/client';

const POLL_MS = 5000; // refresh every 5 s

function fmtDuration(secs: number) {
  if (secs <= 0) return '0 s';
  if (secs < 60) return `${Math.round(secs)} s`;
  return `${Math.floor(secs / 60)} min ${Math.round(secs % 60)} s`;
}

function ts(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

interface AnomalyAlert { id: string; title: string; detail: string; time: string; }

export default function DashboardPage() {
  const [farms, setFarms]           = useState<Farm[]>([]);
  const [devices, setDevices]       = useState<Device[]>([]);
  const [selectedFarm, setSelectedFarm]     = useState<number | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<number | null>(null);

  const [telemetry, setTelemetry]   = useState<Telemetry[]>([]);
  const [weather, setWeather]       = useState<Weather | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [anomalies, setAnomalies]   = useState<AnomalyAlert[]>([]);
  const [predMode, setPredMode]     = useState<'ml' | 'math'>('ml');
  const [watering, setWatering]     = useState(false);
  const [lastWatered, setLastWatered] = useState<string | null>(null);
  
  // AI Advisor state
  const [aiAdvice, setAiAdvice]     = useState<AiAdvice | null>(null);
  const [aiQuestion, setAiQuestion] = useState('');
  const [aiLoading, setAiLoading]   = useState(false);
  const [aiError, setAiError]       = useState('');
  
  const seenAnomaly = useRef<Set<number>>(new Set());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAiAdvice = useCallback(async (q?: string) => {
    if (!selectedDevice) return;
    setAiLoading(true);
    setAiError('');
    try {
      const data = await aiApi.getAdvice(selectedDevice, q);
      setAiAdvice(data);
      if (q) setAiQuestion('');
    } catch (err: unknown) {
      setAiError(err instanceof Error ? err.message : 'AI connection failed');
    } finally {
      setAiLoading(false);
    }
  }, [selectedDevice]);

  useEffect(() => {
    if (selectedDevice) {
      fetchAiAdvice();
    }
  }, [selectedDevice, fetchAiAdvice]);

  // ── Fetch farms & devices on mount ──────────────────────────────
  useEffect(() => {
    farmsApi.list().then(fs => {
      setFarms(fs);
      if (fs.length > 0) setSelectedFarm(fs[0].id);
    });
  }, []);

  useEffect(() => {
    if (!selectedFarm) return;
    devicesApi.list(selectedFarm).then(ds => {
      setDevices(ds);
      if (ds.length > 0) setSelectedDevice(ds[0].id);
    });
  }, [selectedFarm]);

  // ── Poll telemetry, weather and prediction ─────────────────────
  const fetchAll = useCallback(async () => {
    if (!selectedDevice) return;
    try {
      const [tdata, wdata, pdata] = await Promise.all([
        telemetryApi.get(selectedDevice, 60),
        weatherApi.get(),
        predictionsApi.schedule(selectedDevice, predMode),
      ]);
      setTelemetry(tdata);
      setWeather(wdata);
      setPrediction(pdata);

      // Detect new anomalies
      tdata
        .filter(t => t.is_anomaly && !seenAnomaly.current.has(t.id))
        .forEach(t => {
          seenAnomaly.current.add(t.id);
          const reasons: string[] = [];
          if (t.soil_moisture < 15) reasons.push(`moisture ${t.soil_moisture.toFixed(1)}% < 15%`);
          if (t.temperature   > 45) reasons.push(`temp ${t.temperature.toFixed(1)}°C > 45°C`);
          if (t.ph < 4.5)           reasons.push(`pH ${t.ph.toFixed(2)} < 4.5`);
          if (t.ph > 8.5)           reasons.push(`pH ${t.ph.toFixed(2)} > 8.5`);
          setAnomalies(prev => [{
            id: String(t.id),
            title: '⚡ EDGE ALERT',
            detail: reasons.join(' · ') || 'Anomalous reading detected',
            time: ts(t.timestamp),
          }, ...prev].slice(0, 20));
        });
    } catch {/* backend may not be ready */ }
  }, [selectedDevice, predMode]);

  useEffect(() => {
    fetchAll();
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(fetchAll, POLL_MS);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchAll]);

  // ── Manual watering trigger ─────────────────────────────────────
  async function triggerWatering() {
    if (!selectedDevice || !prediction) return;
    setWatering(true);
    try {
      await wateringApi.log(
        selectedDevice,
        Math.round(prediction.recommended_duration_seconds),
        true,
      );
      setLastWatered(new Date().toLocaleTimeString());
    } finally { setWatering(false); }
  }

  // ── Derived series for sparklines ──────────────────────────────
  const series = {
    moisture: telemetry.map(t => t.soil_moisture),
    ph:       telemetry.map(t => t.ph),
    temp:     telemetry.map(t => t.temperature),
    humidity: telemetry.map(t => t.humidity),
  };
  const latest = telemetry[telemetry.length - 1] ?? null;

  // Weather icon helper
  function weatherIcon(cond: string) {
    if (cond.includes('Rain'))   return '🌧';
    if (cond.includes('Cloudy')) return '⛅';
    return '☀️';
  }

  return (
    <div className="animate-in">
      {/* ── Page header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">LIVE MONITOR</h1>
          <p className="page-subtitle">
            <span className="pulse-dot" style={{ marginRight: 6 }} />
            Auto-refresh every {POLL_MS / 1000} s · {new Date().toLocaleDateString()}
          </p>
        </div>
        <div className="flex gap-2" style={{ flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {/* Farm selector */}
          <select
            id="farm-select"
            className="input-field"
            style={{ width: 'auto', padding: '0.5rem 1rem' }}
            value={selectedFarm ?? ''}
            onChange={e => setSelectedFarm(Number(e.target.value))}
          >
            {farms.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
          {/* Device selector */}
          <select
            id="device-select"
            className="input-field"
            style={{ width: 'auto', padding: '0.5rem 1rem' }}
            value={selectedDevice ?? ''}
            onChange={e => setSelectedDevice(Number(e.target.value))}
          >
            {devices.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <button
            id="refresh-btn"
            className="btn btn-green btn-sm"
            onClick={fetchAll}
          >⟳ REFRESH</button>
        </div>
      </div>

      {/* ── KPI tiles ── */}
      <div className="metric-grid mb-4">
        <div className="metric-tile">
          <div className="metric-label">Soil Moisture</div>
          <div className={`metric-value ${
            !latest ? 'metric-white'
            : latest.soil_moisture < 25 ? 'metric-red'
            : latest.soil_moisture < 45 ? 'metric-orange'
            : 'metric-green'
          }`}>
            {latest ? latest.soil_moisture.toFixed(1) : '—'}
          </div>
          <div className="metric-unit">% volumetric</div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">Soil pH</div>
          <div className={`metric-value ${
            !latest ? 'metric-white'
            : (latest.ph < 5.5 || latest.ph > 7.5) ? 'metric-orange'
            : 'metric-green'
          }`}>
            {latest ? latest.ph.toFixed(2) : '—'}
          </div>
          <div className="metric-unit">pH scale</div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">Temperature</div>
          <div className={`metric-value ${
            !latest ? 'metric-white'
            : latest.temperature > 40 ? 'metric-red'
            : latest.temperature > 30 ? 'metric-orange'
            : 'metric-green'
          }`}>
            {latest ? latest.temperature.toFixed(1) : '—'}
          </div>
          <div className="metric-unit">°C ambient</div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">Humidity</div>
          <div className="metric-value metric-white">
            {latest ? latest.humidity.toFixed(1) : '—'}
          </div>
          <div className="metric-unit">% relative</div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">Anomalies</div>
          <div className={`metric-value ${anomalies.length > 0 ? 'metric-red' : 'metric-green'}`}>
            {anomalies.length}
          </div>
          <div className="metric-unit">this session</div>
        </div>
        <div className="metric-tile">
          <div className="metric-label">Readings</div>
          <div className="metric-value metric-white">{telemetry.length}</div>
          <div className="metric-unit">total samples</div>
        </div>
      </div>

      {/* ── Charts row ── */}
      <div className="grid-2 mb-4">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Soil Moisture History</span>
            <span className={`badge ${series.moisture.at(-1) ?? 0 < 25 ? 'badge-red' : 'badge-green'}`}>
              {series.moisture.length > 0 ? `${(series.moisture.at(-1) ?? 0).toFixed(1)}%` : 'No data'}
            </span>
          </div>
          <LineChart data={series.moisture} color="#39ff14" label="Soil Moisture (%)" unit="%" min={0} max={100} />
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-title">Soil pH History</span>
            <span className="badge badge-green">
              {series.ph.length > 0 ? (series.ph.at(-1) ?? 0).toFixed(2) : 'No data'}
            </span>
          </div>
          <LineChart data={series.ph} color="#ffe600" label="pH Level" unit="" min={4} max={9} />
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-title">Temperature (°C)</span>
            <span className={`badge ${(series.temp.at(-1) ?? 0) > 35 ? 'badge-orange' : 'badge-green'}`}>
              {series.temp.length > 0 ? `${(series.temp.at(-1) ?? 0).toFixed(1)}°C` : 'No data'}
            </span>
          </div>
          <LineChart data={series.temp} color="#ff6b00" label="Temperature (°C)" unit="°C" min={10} max={50} />
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-title">Humidity (%)</span>
            <span className="badge badge-green">
              {series.humidity.length > 0 ? `${(series.humidity.at(-1) ?? 0).toFixed(1)}%` : 'No data'}
            </span>
          </div>
          <LineChart data={series.humidity} color="#00cfff" label="Relative Humidity (%)" unit="%" min={0} max={100} />
        </div>
      </div>

      {/* ── Weather + Prediction row ── */}
      <div className="grid-2 mb-4">
        {/* Weather widget */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Weather Forecast — {weather?.location ?? '…'}</span>
          </div>
          {weather ? (
            <>
              <div className="weather-widget mb-2">
                <div style={{ fontSize: '2.5rem' }}>{weatherIcon(weather.condition)}</div>
                <div>
                  <div className="weather-temp">{weather.temperature.toFixed(1)}°C</div>
                  <div className="weather-condition">{weather.condition}</div>
                </div>
                <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                  <p className="text-xs text-muted">Humidity</p>
                  <p className="text-sm" style={{ color: '#00cfff' }}>{weather.humidity.toFixed(0)}%</p>
                  <p className="text-xs text-muted mt-1">Rain Prob.</p>
                  <p className="text-sm" style={{ color: weather.precipitation_probability > 60 ? '#ff6b00' : '#39ff14' }}>
                    {weather.precipitation_probability.toFixed(0)}%
                  </p>
                  <p className="text-xs text-muted mt-1">Cloud Cover</p>
                  <p className="text-sm">{weather.cloud_cover.toFixed(0)}%</p>
                </div>
              </div>
              {weather.precipitation_probability > 60 && (
                <div style={{ padding: '0.6rem 0.8rem', border: '2px solid #ff6b00', color: '#ff6b00', fontSize: '0.75rem' }}>
                  ⚠ Rain expected — irrigation automatically reduced
                </div>
              )}
            </>
          ) : (
            <p className="text-muted text-sm">Fetching forecast…</p>
          )}
        </div>

        {/* Prediction panel */}
        <div>
          <div className="prediction-panel mb-2">
            <div className="card-header">
              <span className="card-title">Optimal Irrigation Schedule</span>
              <div className="flex gap-1">
                <button
                  id="pred-ml-btn"
                  className={`btn btn-sm ${predMode === 'ml' ? 'btn-green' : ''}`}
                  onClick={() => setPredMode('ml')}
                >ML</button>
                <button
                  id="pred-math-btn"
                  className={`btn btn-sm ${predMode === 'math' ? 'btn-green' : ''}`}
                  onClick={() => setPredMode('math')}
                >MATH</button>
              </div>
            </div>
            {prediction ? (
              <>
                <div>
                  <div className="prediction-duration">
                    {fmtDuration(prediction.recommended_duration_seconds)}
                  </div>
                  <div className="prediction-unit">recommended watering duration</div>
                </div>
                <div className="prediction-meta">
                  <span>Model: <strong style={{ color: '#fff' }}>{prediction.model_used.replace('_', ' ')}</strong></span>
                  <span>Moisture: <strong style={{ color: '#fff' }}>{prediction.current_soil_moisture.toFixed(1)}%</strong></span>
                  <span>Rain prob: <strong style={{ color: '#fff' }}>{prediction.weather_precipitation_probability.toFixed(0)}%</strong></span>
                  <span>Cloud: <strong style={{ color: '#fff' }}>{prediction.weather_cloud_cover.toFixed(0)}%</strong></span>
                  <span style={{ marginLeft: 'auto', color: '#333' }}>calc @ {ts(prediction.timestamp)}</span>
                </div>
              </>
            ) : (
              <p className="text-muted text-sm">Awaiting telemetry data…</p>
            )}
          </div>

          <button
            id="water-now-btn"
            className={`btn ${prediction && prediction.recommended_duration_seconds > 0 ? 'btn-green' : 'btn-orange'} btn-lg w-full`}
            style={{ justifyContent: 'center' }}
            disabled={watering || !prediction}
            onClick={triggerWatering}
          >
            {watering ? '[ WATERING… ]' : '[ ▶ WATER NOW (MANUAL) ]'}
          </button>
          {lastWatered && (
            <p className="text-xs text-muted mt-1" style={{ textAlign: 'center' }}>
              Last watered: {lastWatered}
            </p>
          )}
        </div>
      </div>

      {/* ── Gemini AI Advisor ── */}
      <div className="card mb-4" style={{ border: '4px solid #000', boxShadow: '4px 4px 0px #000', background: '#0a0a0a', color: '#fff' }}>
        <div className="card-header" style={{ borderBottom: '2px solid #1c1c1c', paddingBottom: '0.75rem', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="card-title" style={{ color: '#39ff14', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.2rem', fontWeight: 'bold' }}>
            🤖 GEMINI AI AGRI-ADVISOR
          </span>
          <span className="badge badge-green" style={{ background: '#39ff14', color: '#000', border: '2px solid #000', fontWeight: 'bold' }}>
            Powered by Gemini 1.5 Flash
          </span>
        </div>
        
        <div className="grid-2" style={{ gap: '1.5rem' }}>
          {/* Left half: AI Assessment Output */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <h3 style={{ fontSize: '0.9rem', color: '#888', textTransform: 'uppercase', letterSpacing: '1px' }}>
              ✦ Live Telemetry Assessment
            </h3>
            
            {aiLoading && !aiAdvice ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#888', fontStyle: 'italic', fontFamily: 'var(--mono)', border: '2px dashed #333' }}>
                <span className="pulse-dot" style={{ display: 'inline-block', marginRight: 10 }} />
                Analyzing soil profile & forecast models...
              </div>
            ) : aiError ? (
              <div style={{ padding: '1rem', border: '2px solid #ff2d2d', color: '#ff2d2d', fontSize: '0.8rem', fontFamily: 'var(--mono)' }}>
                ⚠ Error fetching advice: {aiError}
              </div>
            ) : aiAdvice ? (
              <div style={{
                background: '#111',
                border: '2px solid #333',
                padding: '1rem',
                fontSize: '0.85rem',
                lineHeight: '1.5',
                fontFamily: 'var(--mono)',
                color: '#ececec',
                maxHeight: '220px',
                overflowY: 'auto',
                whiteSpace: 'pre-wrap'
              }}>
                {aiAdvice.advice}
              </div>
            ) : (
              <p className="text-muted text-sm" style={{ fontStyle: 'italic' }}>No advice fetched yet.</p>
            )}
            
            {aiAdvice && (
              <p className="text-xs text-muted" style={{ fontFamily: 'var(--mono)', marginTop: '0.2rem' }}>
                Last analysis generated: {new Date(aiAdvice.timestamp).toLocaleString()}
              </p>
            )}
          </div>
          
          {/* Right half: Chat / Inquiry Form */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <h3 style={{ fontSize: '0.9rem', color: '#888', textTransform: 'uppercase', letterSpacing: '1px' }}>
                ✦ Ask Custom Agronomic Questions
              </h3>
              <p className="text-xs text-muted" style={{ marginBottom: '0.5rem' }}>
                Ask Gemini about crop recommendations, soil treatments, or abnormal metric analysis.
              </p>
              
              <textarea
                className="input-field"
                style={{
                  width: '100%',
                  height: '100px',
                  background: '#000',
                  color: '#fff',
                  border: '2px solid #333',
                  padding: '0.75rem',
                  fontSize: '0.85rem',
                  fontFamily: 'var(--mono)',
                  resize: 'none',
                }}
                placeholder="e.g., 'What crops would be best suited for this pH level?' or 'How does the forecasted rain affect my tomato patch?'"
                value={aiQuestion}
                onChange={e => setAiQuestion(e.target.value)}
                disabled={aiLoading}
              />
            </div>
            
            <div className="flex gap-2" style={{ marginTop: '0.5rem' }}>
              <button
                className="btn btn-green btn-lg"
                style={{ flex: 1, justifyContent: 'center', background: '#39ff14', color: '#000', border: '2px solid #000', fontWeight: 'bold' }}
                disabled={aiLoading || !selectedDevice || !aiQuestion.trim()}
                onClick={() => fetchAiAdvice(aiQuestion)}
              >
                {aiLoading ? '[ CONSULTING GEMINI... ]' : '[ GET ADVISORY INSIGHT → ]'}
              </button>
              
              <button
                className="btn btn-sm"
                style={{ background: '#000', color: '#888', border: '2px solid #333' }}
                disabled={aiLoading || !selectedDevice}
                onClick={() => fetchAiAdvice()}
                title="Refresh Assessment"
              >
                ⟳ RE-ASSESS SOIL
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Anomaly Feed ── */}
      <div className="card card-orange">
        <div className="card-header">
          <span className="card-title">Edge Anomaly Alert Feed</span>
          <span className={`badge ${anomalies.length > 0 ? 'badge-orange' : 'badge-green'}`}>
            {anomalies.length > 0 ? `${anomalies.length} ALERTS` : 'ALL CLEAR'}
          </span>
        </div>
        {anomalies.length === 0 ? (
          <p className="text-muted text-sm" style={{ padding: '1rem 0' }}>
            ✓ No anomalies detected. Edge filters nominal.
          </p>
        ) : (
          <div className="anomaly-feed">
            {anomalies.map(a => (
              <div key={a.id} className="anomaly-item">
                <div className="anomaly-icon">⚡</div>
                <div className="anomaly-content">
                  <div className="anomaly-title">{a.title}</div>
                  <div className="anomaly-detail">{a.detail}</div>
                  <div className="anomaly-time">{a.time}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
