import { useStore } from '../store/store';

export function TargetsView() {
  const { targets, selectedTarget, setSelectedTarget } = useStore();

  if (targets.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">&#9737;</div>
        <div>Load accessible NEA targets from the sidebar</div>
      </div>
    );
  }

  return (
    <div style={{
      width: '100%', height: '100%', overflow: 'auto',
      padding: '20px 28px',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        marginBottom: '14px',
      }}>
        <h2 style={{
          color: 'var(--text-primary)', fontSize: '15px', fontWeight: 600, margin: 0,
          fontFamily: 'var(--font-mono)', letterSpacing: '0.5px',
        }}>
          Accessible Near-Earth Asteroids
        </h2>
        <span style={{ color: 'var(--text-dim)', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
          {targets.length} targets | NASA NHATS
        </span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%', borderCollapse: 'collapse',
          fontSize: '12px', fontFamily: 'var(--font-mono)',
        }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--panel-border)' }}>
              {['#', 'Designation', 'Min Δv', 'Duration', 'H mag', 'Size (m)', 'Trajectories'].map(h => (
                <th key={h} style={{
                  padding: '8px 10px', textAlign: h === '#' ? 'center' : 'left',
                  color: 'var(--text-dim)', fontSize: '9px', textTransform: 'uppercase',
                  letterSpacing: '0.8px', fontWeight: 500,
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {targets.map((t, i) => {
              const isSelected = selectedTarget?.des === t.des;
              return (
                <tr
                  key={t.des}
                  onClick={() => setSelectedTarget(isSelected ? null : t)}
                  style={{
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(0, 212, 224, 0.06)' : 'transparent',
                    borderBottom: '1px solid var(--panel-border)',
                    borderLeft: isSelected ? '2px solid var(--cyan)' : '2px solid transparent',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.background = 'rgba(26, 37, 53, 0.4)';
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <td style={{ padding: '7px 10px', textAlign: 'center', color: 'var(--text-dim)' }}>{i + 1}</td>
                  <td style={{ padding: '7px 10px', color: isSelected ? 'var(--cyan)' : 'var(--text-primary)' }}>{t.des}</td>
                  <td style={{ padding: '7px 10px' }}>
                    <span style={{ color: t.min_dv < 4 ? 'var(--cyan)' : t.min_dv < 5 ? 'var(--amber)' : 'var(--text-primary)' }}>
                      {t.min_dv.toFixed(3)}
                    </span>
                    <span style={{ color: 'var(--text-dim)', marginLeft: '3px', fontSize: '10px' }}>km/s</span>
                  </td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-secondary)' }}>{t.min_dv_dur}d</td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-secondary)' }}>{t.h.toFixed(1)}</td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-secondary)' }}>
                    {t.min_size_m > 0 ? `${t.min_size_m}–${t.max_size_m}` : '—'}
                  </td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-secondary)' }}>{t.n_via.toLocaleString()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Selected target detail popup */}
      {selectedTarget && (
        <div style={{
          position: 'fixed', bottom: '16px', right: '16px',
          background: 'var(--surface)', border: '1px solid var(--panel-border)',
          borderLeft: '2px solid var(--cyan)', borderRadius: '4px',
          padding: '14px 18px', maxWidth: '320px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
          backdropFilter: 'blur(8px)',
        }}>
          <div style={{
            fontSize: '14px', fontWeight: 600, color: 'var(--cyan)',
            fontFamily: 'var(--font-mono)', marginBottom: '8px',
          }}>
            {selectedTarget.des}
            {selectedTarget.fullname && selectedTarget.fullname !== selectedTarget.des && (
              <span style={{ color: 'var(--text-dim)', fontSize: '11px', marginLeft: '8px', fontWeight: 400 }}>
                {selectedTarget.fullname}
              </span>
            )}
          </div>
          <div style={{
            fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.7,
            fontFamily: 'var(--font-mono)',
          }}>
            <Row label="Min Δv" value={`${selectedTarget.min_dv.toFixed(3)} km/s`} />
            <Row label="Mission dur" value={`${selectedTarget.min_dv_dur} days`} />
            <Row label="Min duration" value={`${selectedTarget.min_dur} days`} />
            <Row label="Size" value={selectedTarget.min_size_m > 0 ? `${selectedTarget.min_size_m}–${selectedTarget.max_size_m} m` : 'Unknown'} />
            <Row label="H magnitude" value={selectedTarget.h.toFixed(1)} />
            <Row label="Trajectories" value={selectedTarget.n_via.toLocaleString()} />
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
      <span style={{ color: 'var(--text-dim)' }}>{label}</span>
      <span style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  );
}
