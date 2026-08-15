/**
 * Portföy dağılımı halka grafiği.
 *
 * Sunucu bileşeni — JavaScript göndermiyoruz, SVG doğrudan HTML'e gömülüyor.
 * Grafik kütüphanesi eklemedik: tek bir halka için 200KB bağımlılık gereksiz.
 */

const COLORS = {
  BTC: "#f0932b",
  ETH: "#7d8cf5",
  HYPE: "#37d399",
  Nakit: "#3d4756",
};

const R = 42;
const C = 2 * Math.PI * R;

const fmt = (n) =>
  n.toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

/**
 * @param {{label:string, value:number}[]} slices - USD cinsinden
 */
export default function Donut({ slices, total }) {
  const real = slices.filter((s) => s.value > 0.5);
  if (!real.length || !total) return null;

  let offset = 0;
  const arcs = real.map((s) => {
    const frac = s.value / total;
    const len = frac * C;
    const arc = {
      ...s,
      frac,
      dash: `${len} ${C - len}`,
      // Negatif offset saat yönünde ilerletir; -90° rotasyon tepeden başlatır.
      dashOffset: -offset,
    };
    offset += len;
    return arc;
  });

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 110 110" className="donut" role="img"
           aria-label="Portföy dağılımı">
        {arcs.map((a) => (
          <circle
            key={a.label}
            cx="55" cy="55" r={R}
            fill="none"
            stroke={COLORS[a.label] || "#666"}
            strokeWidth="16"
            strokeDasharray={a.dash}
            strokeDashoffset={a.dashOffset}
            transform="rotate(-90 55 55)"
          />
        ))}
      </svg>

      <ul className="donut-legend">
        {arcs.map((a) => (
          <li key={a.label}>
            <span className="dot" style={{ background: COLORS[a.label] || "#666" }} />
            <span className="lg-name">{a.label}</span>
            <span className="lg-pct">%{Math.round(a.frac * 100)}</span>
            <span className="lg-usd">${fmt(a.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
