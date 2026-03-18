import { useRef, useEffect, useCallback } from 'react';
import { useStore } from '../store/store';
import { getTransfer } from '../lib/api';
import type { PorkchopData } from '../lib/api';

// Viridis-like colormap (dark blue → cyan → yellow)
function dvToColor(dv: number, minDv: number, maxDv: number): string {
  const t = Math.max(0, Math.min(1, (dv - minDv) / (maxDv - minDv)));
  // Dark blue → teal → green → yellow
  const r = Math.round(t < 0.5 ? 20 + t * 200 : 120 + (t - 0.5) * 270);
  const g = Math.round(t < 0.33 ? 10 + t * 400 : t < 0.66 ? 140 + (t - 0.33) * 200 : 200 + (t - 0.66) * 160);
  const b = Math.round(t < 0.5 ? 80 + (1 - t) * 150 : 80 - (t - 0.5) * 140);
  return `rgb(${r},${g},${b})`;
}

function formatDate(utcStr: string): string {
  if (!utcStr) return '';
  return utcStr.slice(0, 10);
}

export function PorkchopPlot() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { porkchop, setDepartureDate, setArrivalDate, setViewMode } = useStore();

  const draw = useCallback((data: PorkchopData) => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = container.getBoundingClientRect();
    const margin = { top: 40, right: 20, bottom: 60, left: 70 };
    const width = rect.width;
    const height = rect.height;
    canvas.width = width * window.devicePixelRatio;
    canvas.height = height * window.devicePixelRatio;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;
    const rows = data.dv_total.length;
    const cols = data.dv_total[0]?.length || 0;

    // Find delta-v range for color mapping
    let minDv = Infinity, maxDv = -Infinity;
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        const v = data.dv_total[i][j];
        if (v != null) {
          if (v < minDv) minDv = v;
          if (v > maxDv) maxDv = v;
        }
      }
    }
    // Clamp max for better contrast
    maxDv = Math.min(maxDv, minDv + 30);

    // Background
    ctx.fillStyle = '#0a0e1a';
    ctx.fillRect(0, 0, width, height);

    // Draw heatmap cells
    const cellW = plotW / cols;
    const cellH = plotH / rows;
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        const v = data.dv_total[i][j];
        if (v == null) continue;
        ctx.fillStyle = dvToColor(v, minDv, maxDv);
        ctx.fillRect(
          margin.left + j * cellW,
          margin.top + i * cellH,
          Math.ceil(cellW) + 1,
          Math.ceil(cellH) + 1
        );
      }
    }

    // Draw optimal marker
    if (data.optimal) {
      const depIdx = data.dep_dates.findIndex(d => d === data.optimal!.dep_utc);
      const arrIdx = data.arr_dates.findIndex(d => d === data.optimal!.arr_utc);

      // Find closest indices if exact match fails
      let oi = depIdx >= 0 ? depIdx : 0;
      let oj = arrIdx >= 0 ? arrIdx : 0;
      if (depIdx < 0 || arrIdx < 0) {
        // Find the minimum cell
        let bestVal = Infinity;
        for (let i = 0; i < rows; i++) {
          for (let j = 0; j < cols; j++) {
            const v = data.dv_total[i][j];
            if (v != null && v < bestVal) {
              bestVal = v;
              oi = i;
              oj = j;
            }
          }
        }
      }

      const ox = margin.left + oj * cellW + cellW / 2;
      const oy = margin.top + oi * cellH + cellH / 2;

      // Crosshair
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(ox, oy, 8, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(ox - 12, oy); ctx.lineTo(ox + 12, oy);
      ctx.moveTo(ox, oy - 12); ctx.lineTo(ox, oy + 12);
      ctx.stroke();

      // Label
      ctx.fillStyle = '#ffffff';
      ctx.font = '11px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(
        `${data.optimal.dv_total.toFixed(2)} km/s`,
        ox + 14, oy - 4
      );
      ctx.fillStyle = '#6b7a96';
      ctx.font = '10px monospace';
      ctx.fillText(
        `${Math.round(data.optimal.tof_days)}d`,
        ox + 14, oy + 10
      );
    }

    // Axes
    ctx.strokeStyle = '#1e2a45';
    ctx.lineWidth = 1;
    // Left axis
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, margin.top + plotH);
    ctx.lineTo(margin.left + plotW, margin.top + plotH);
    ctx.stroke();

    // X-axis labels (arrival dates)
    ctx.fillStyle = '#6b7a96';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    const xLabelCount = Math.min(6, cols);
    for (let k = 0; k < xLabelCount; k++) {
      const idx = Math.round(k * (cols - 1) / (xLabelCount - 1));
      const x = margin.left + idx * cellW + cellW / 2;
      const label = formatDate(data.arr_dates[idx]);
      ctx.save();
      ctx.translate(x, margin.top + plotH + 12);
      ctx.rotate(Math.PI / 4);
      ctx.textAlign = 'left';
      ctx.fillText(label, 0, 0);
      ctx.restore();
    }

    // Y-axis labels (departure dates)
    ctx.textAlign = 'right';
    const yLabelCount = Math.min(6, rows);
    for (let k = 0; k < yLabelCount; k++) {
      const idx = Math.round(k * (rows - 1) / (yLabelCount - 1));
      const y = margin.top + idx * cellH + cellH / 2;
      ctx.fillText(formatDate(data.dep_dates[idx]), margin.left - 6, y + 3);
    }

    // Axis titles
    ctx.fillStyle = '#8899aa';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Arrival Date', margin.left + plotW / 2, height - 6);

    ctx.save();
    ctx.translate(14, margin.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Departure Date', 0, 0);
    ctx.restore();

    // Title
    ctx.fillStyle = '#c8d0e0';
    ctx.font = 'bold 13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(
      `${data.departure_body} → ${data.arrival_body}  |  Total Δv (km/s)`,
      width / 2, 20
    );

    // Color bar
    const barX = margin.left + plotW + 6;
    const barW = 12;
    const barH = plotH;
    for (let i = 0; i < barH; i++) {
      const t = i / barH;
      const dv = minDv + t * (maxDv - minDv);
      ctx.fillStyle = dvToColor(dv, minDv, maxDv);
      ctx.fillRect(barX, margin.top + i, barW, 2);
    }
    ctx.fillStyle = '#6b7a96';
    ctx.font = '9px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${minDv.toFixed(1)}`, barX + barW + 3, margin.top + 6);
    ctx.fillText(`${maxDv.toFixed(1)}`, barX + barW + 3, margin.top + barH);
  }, []);

  // Redraw when porkchop data changes
  useEffect(() => {
    if (porkchop) draw(porkchop);
  }, [porkchop, draw]);

  // Redraw on resize
  useEffect(() => {
    const handleResize = () => { if (porkchop) draw(porkchop); };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [porkchop, draw]);

  // Click handler: select departure/arrival dates from plot
  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!porkchop || !canvasRef.current || !containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const margin = { top: 40, right: 20, bottom: 60, left: 70 };
    const plotW = rect.width - margin.left - margin.right;
    const plotH = rect.height - margin.top - margin.bottom;

    const x = e.clientX - rect.left - margin.left;
    const y = e.clientY - rect.top - margin.top;

    if (x < 0 || x > plotW || y < 0 || y > plotH) return;

    const rows = porkchop.dv_total.length;
    const cols = porkchop.dv_total[0]?.length || 0;
    const i = Math.floor(y / plotH * rows);
    const j = Math.floor(x / plotW * cols);

    if (i >= 0 && i < rows && j >= 0 && j < cols) {
      const dv = porkchop.dv_total[i][j];
      if (dv != null) {
        const depDate = formatDate(porkchop.dep_dates[i]);
        const arrDate = formatDate(porkchop.arr_dates[j]);
        setDepartureDate(depDate);
        setArrivalDate(arrDate);
        setViewMode('solar-system');
        // Auto-compute the transfer for the clicked dates
        const state = useStore.getState();
        useStore.setState({ transferLoading: true, referenceMission: null });
        getTransfer(state.departureBody, state.arrivalBody, depDate, arrDate)
          .then(result => useStore.setState({ transfer: result, transferLoading: false }))
          .catch(() => useStore.setState({ transferLoading: false }));
      }
    }
  }, [porkchop, setDepartureDate, setArrivalDate, setViewMode]);

  if (!porkchop) {
    return (
      <div style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-dim)',
        fontSize: '14px',
        flexDirection: 'column',
        gap: '8px',
      }}>
        <div style={{ fontSize: '24px', opacity: 0.3 }}>&#9673;</div>
        <div>Generate a porkchop plot from the sidebar</div>
        <div style={{ fontSize: '11px', opacity: 0.5 }}>
          Select departure/arrival bodies and click "Generate Porkchop Plot"
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        style={{ cursor: 'crosshair', display: 'block' }}
      />
      <div style={{
        position: 'absolute',
        bottom: '8px',
        left: '50%',
        transform: 'translateX(-50%)',
        fontSize: '10px',
        color: 'var(--text-dim)',
        background: 'rgba(10,14,26,0.8)',
        padding: '4px 10px',
        borderRadius: '4px',
      }}>
        Click to select transfer dates → auto-computes in 3D view
      </div>
    </div>
  );
}
