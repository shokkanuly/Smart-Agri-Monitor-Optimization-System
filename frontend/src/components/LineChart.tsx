// src/components/LineChart.tsx
// Lightweight pure-canvas SVG-free line chart — no external chart lib.

import { useEffect, useRef } from 'react';

interface LineChartProps {
  data: number[];
  color?: string;
  label?: string;
  unit?: string;
  height?: number;
  min?: number;
  max?: number;
}

export default function LineChart({
  data,
  color = '#39ff14',
  label = '',
  unit = '',
  height = 120,
  min,
  max,
}: LineChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length < 2) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // DPI scaling
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.offsetWidth;
    const h = height;
    canvas.width  = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    // Clear
    ctx.clearRect(0, 0, w, h);

    // Bounds
    const lo = min ?? Math.min(...data);
    const hi = max ?? Math.max(...data);
    const range = hi - lo || 1;

    const pad = { top: 12, right: 8, bottom: 24, left: 40 };
    const cw = w - pad.left - pad.right;
    const ch = h - pad.top - pad.bottom;

    const toX = (i: number) => pad.left + (i / (data.length - 1)) * cw;
    const toY = (v: number) => pad.top + ch - ((v - lo) / range) * ch;

    // Grid lines (subtle)
    ctx.strokeStyle = '#222';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (ch / 4) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + cw, y);
      ctx.stroke();

      // Y labels
      const val = hi - (range / 4) * i;
      ctx.fillStyle = '#444';
      ctx.font = `9px 'JetBrains Mono', monospace`;
      ctx.textAlign = 'right';
      ctx.fillText(val.toFixed(0), pad.left - 4, y + 3);
    }

    // Gradient fill below line
    const gradient = ctx.createLinearGradient(0, pad.top, 0, pad.top + ch);
    gradient.addColorStop(0, color + '33');
    gradient.addColorStop(1, color + '00');
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(data[0]));
    for (let i = 1; i < data.length; i++) ctx.lineTo(toX(i), toY(data[i]));
    ctx.lineTo(toX(data.length - 1), pad.top + ch);
    ctx.lineTo(toX(0), pad.top + ch);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.moveTo(toX(0), toY(data[0]));
    for (let i = 1; i < data.length; i++) ctx.lineTo(toX(i), toY(data[i]));
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Latest value dot
    const lastX = toX(data.length - 1);
    const lastY = toY(data[data.length - 1]);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    // Latest value label
    ctx.fillStyle = color;
    ctx.font = `bold 10px 'JetBrains Mono', monospace`;
    ctx.textAlign = 'right';
    ctx.fillText(`${data[data.length - 1].toFixed(1)}${unit}`, lastX - 6, lastY - 6);

  }, [data, color, height, min, max, unit]);

  return (
    <div className="chart-container">
      {label && <div className="chart-label">{label}</div>}
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: `${height}px`, display: 'block' }}
      />
    </div>
  );
}
