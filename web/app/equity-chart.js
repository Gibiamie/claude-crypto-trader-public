/**
 * Zaman içinde portföy değeri — her karakter bir çizgi, HODL kesikli çizgi.
 * Alım (yeşil ▲) ve satım (kırmızı ▼) yapılan saatler çizginin üstünde işaretli.
 *
 * Donut gibi: sunucu bileşeni, saf SVG. Grafik kütüphanesi yok.
 *
 * ponytail: saatlik veri çoğaldıkça alım/satım üçgenleri sıklaşabilir; şimdilik
 * bilgi taşıyor (kim çok işlem yapıyor görülüyor). Kalabalık olursa günlük
 * gruplama eklenir.
 */

export const AGENT_COLORS = {
  temkinli: "#5b9bf5",
  dengeli: "#c9884a",
  risksever: "#a97bf0",
};
const FALLBACK = ["#5b9bf5", "#c9884a", "#a97bf0", "#37d399", "#f2678a"];
export const colorFor = (agent, i = 0) => AGENT_COLORS[agent] || FALLBACK[i % FALLBACK.length];
const UP = "#37d399";
const DOWN = "#f2678a";
const GRID = "#232a32";
const AXIS = "#8b97a6";

const W = 760;
const H = 340;
const PAD = { l: 58, r: 16, t: 16, b: 34 };
const PW = W - PAD.l - PAD.r;
const PH = H - PAD.t - PAD.b;

const money = (n) => "$" + Math.round(n).toLocaleString("tr-TR");
const shortDate = (t) =>
  new Date(t).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });

export default function EquityChart({ data }) {
  const series = data?.series || [];
  const hodl = data?.hodl || [];

  const allPts = series.flatMap((s) => s.points);
  if (allPts.length + hodl.length < 2) {
    return (
      <div className="empty">
        Grafik için yeterli veri yok — en az birkaç saat gerekiyor.
      </div>
    );
  }

  // --- ölçek ---
  const ts = [...allPts.map((p) => p.t), ...hodl.map((h) => h.t)];
  const vs = [10000, ...allPts.map((p) => p.equity), ...hodl.map((h) => h.value)];
  let tMin = Math.min(...ts);
  let tMax = Math.max(...ts);
  let yMin = Math.min(...vs);
  let yMax = Math.max(...vs);
  const yPad = (yMax - yMin) * 0.08 || 100;
  yMin -= yPad;
  yMax += yPad;
  if (tMax === tMin) tMax = tMin + 1;

  const x = (t) => PAD.l + ((t - tMin) / (tMax - tMin)) * PW;
  const y = (v) => PAD.t + ((yMax - v) / (yMax - yMin)) * PH;

  const yTicks = [0, 1, 2, 3].map((i) => yMin + ((yMax - yMin) * i) / 3);
  const xTicks = [0, 1, 2, 3].map((i) => tMin + ((tMax - tMin) * i) / 3);

  const line = (pts) => pts.map((p) => `${x(p.t).toFixed(1)},${y(p.equity ?? p.value).toFixed(1)}`).join(" ");
  const triUp = (cx, cy) => `M${cx},${cy - 3.2} L${cx - 3},${cy + 2.2} L${cx + 3},${cy + 2.2}Z`;
  const triDown = (cx, cy) => `M${cx},${cy + 3.2} L${cx - 3},${cy - 2.2} L${cx + 3},${cy - 2.2}Z`;

  return (
    <div className="equity-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="equity-chart" role="img"
           aria-label="Zaman içinde portföy değeri">
        {/* yatay ızgara + $ etiketleri */}
        {yTicks.map((v, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke={GRID} strokeWidth="1" />
            <text x={PAD.l - 8} y={y(v) + 3.5} fill={AXIS} fontSize="11" textAnchor="end">
              {money(v)}
            </text>
          </g>
        ))}

        {/* başlangıç $10.000 referans çizgisi */}
        {10000 >= yMin && 10000 <= yMax && (
          <g>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(10000)} y2={y(10000)}
                  stroke={AXIS} strokeWidth="1" strokeDasharray="2 4" opacity="0.5" />
          </g>
        )}

        {/* tarih etiketleri */}
        {xTicks.map((t, i) => (
          <text key={i} x={x(t)} y={H - 12} fill={AXIS} fontSize="11"
                textAnchor={i === 0 ? "start" : i === 3 ? "end" : "middle"}>
            {shortDate(t)}
          </text>
        ))}

        {/* HODL — kesikli */}
        {hodl.length > 1 && (
          <polyline points={line(hodl)} fill="none" stroke={AXIS} strokeWidth="1.6"
                    strokeDasharray="5 4" opacity="0.8" />
        )}

        {/* her karakter */}
        {series.map((s, i) => {
          const c = colorFor(s.agent, i);
          return (
            <g key={s.agent}>
              <polyline points={line(s.points)} fill="none" stroke={c}
                        strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
              {s.points.map((p, j) =>
                p.buy ? <path key={`b${j}`} d={triUp(x(p.t), y(p.equity))} fill={UP} /> : null,
              )}
              {s.points.map((p, j) =>
                p.sell ? <path key={`s${j}`} d={triDown(x(p.t), y(p.equity))} fill={DOWN} /> : null,
              )}
            </g>
          );
        })}
      </svg>

      <ul className="equity-legend">
        {series.map((s, i) => (
          <li key={s.agent}>
            <span className="dot" style={{ background: colorFor(s.agent, i) }} />
            {s.name}
          </li>
        ))}
        <li>
          <span className="dot dash" />
          Alıp bekleyen (HODL)
        </li>
        <li>
          <span className="tri up">▲</span> alım
        </li>
        <li>
          <span className="tri down">▼</span> satım
        </li>
      </ul>
    </div>
  );
}
