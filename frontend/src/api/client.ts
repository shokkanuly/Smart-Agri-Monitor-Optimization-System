// src/api/client.ts
// Typed API wrapper for the FastAPI backend

// In dev, Vite proxies /api → http://127.0.0.1:8000 via vite.config.ts
// Set VITE_API_URL in production to point at the deployed backend.
const BASE = import.meta.env.VITE_API_URL ?? '';

function getToken() {
  return localStorage.getItem('agri_token') ?? '';
}

async function request<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string | number> } = {}
): Promise<T> {
  const { params, ...rest } = options;
  let url = `${BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    ).toString();
    url += `?${qs}`;
  }
  const token = getToken();
  const res = await fetch(url, {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(rest.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Request failed');
  }
  return res.json() as Promise<T>;
}

// ── Auth ─────────────────────────────────────────────────────────
export interface AuthToken { access_token: string; token_type: string; }
export interface User { id: number; username: string; created_at: string; }

export const authApi = {
  register: (username: string, password: string) =>
    request<User>('/api/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),

  login: (username: string, password: string) =>
    request<AuthToken>('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),

  me: () => request<User>('/api/auth/me'),
};

// ── Farms ─────────────────────────────────────────────────────────
export interface Farm { id: number; name: string; location: string; user_id: number; created_at: string; }

export const farmsApi = {
  list: () => request<Farm[]>('/api/farms'),
  create: (name: string, location: string) =>
    request<Farm>('/api/farms', { method: 'POST', body: JSON.stringify({ name, location }) }),
};

// ── Devices ────────────────────────────────────────────────────────
export interface Device { id: number; name: string; api_key: string; farm_id: number; status: string; created_at: string; }

export const devicesApi = {
  list: (farm_id?: number) =>
    request<Device[]>('/api/devices', { params: farm_id ? { farm_id } : {} }),
  create: (name: string, farm_id: number) =>
    request<Device>('/api/devices', { method: 'POST', body: JSON.stringify({ name, farm_id }) }),
};

// ── Telemetry ──────────────────────────────────────────────────────
export interface Telemetry {
  id: number; device_id: number; timestamp: string;
  soil_moisture: number; ph: number; temperature: number; humidity: number; is_anomaly: boolean;
}

export const telemetryApi = {
  get: (device_id: number, limit = 60) =>
    request<Telemetry[]>('/api/telemetry', { params: { device_id, limit } }),
};

// ── Weather ────────────────────────────────────────────────────────
export interface Weather {
  location: string; temperature: number; humidity: number;
  precipitation_probability: number; cloud_cover: number; condition: string; timestamp: string;
}
export const weatherApi = {
  get: () => request<Weather>('/api/weather'),
};

// ── Watering ───────────────────────────────────────────────────────
export interface WateringLog {
  id: number; device_id: number; timestamp: string;
  duration_seconds: number; status: string; manual_override: boolean;
}
export const wateringApi = {
  logs: (device_id: number, limit = 30) =>
    request<WateringLog[]>('/api/watering/logs', { params: { device_id, limit } }),
  log: (device_id: number, duration_seconds: number, manual_override = true) =>
    request<WateringLog>('/api/watering', {
      method: 'POST',
      body: JSON.stringify({ device_id, duration_seconds, manual_override }),
    }),
};

// ── Predictions ────────────────────────────────────────────────────
export interface Prediction {
  device_id: number; current_soil_moisture: number; temperature: number; humidity: number; ph: number;
  weather_precipitation_probability: number; weather_cloud_cover: number;
  recommended_duration_seconds: number; model_used: string; timestamp: string;
}
export const predictionsApi = {
  schedule: (device_id: number, mode: 'ml' | 'math' = 'ml') =>
    request<Prediction>('/api/predictions/schedule', { params: { device_id, mode } }),
  train: () =>
    request<{ status: string; message: string }>('/api/predictions/train', { method: 'POST' }),
};

// ── AI Advisor ──────────────────────────────────────────────────────
export interface AiAdvice {
  advice: string;
  timestamp: string;
}
export const aiApi = {
  getAdvice: (device_id: number, question?: string) =>
    request<AiAdvice>('/api/ai/advise', {
      method: 'POST',
      body: JSON.stringify({ device_id, question }),
    }),
};
