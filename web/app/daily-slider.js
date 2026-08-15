/**
 * Gün gün kart slider'ı — her gün bir kart, eskiden yeniye yatay dizili.
 * Kartta o günün kapanışındaki TOPLAM kâr (equity − 10.000) görünür.
 * CSS scroll-snap ile kaydırılır; grafik kütüphanesi ya da JS yok.
 */

import { colorFor } from "./equity-chart";

const START = 10000;
const signed = (n) =>
  n == null
    ? "—"
    : (n > 0 ? "+" : n < 0 ? "−" : "") + "$" + Math.abs(Math.round(n)).toLocaleString("tr-TR");
const cls = (n) => (n == null ? "" : n > 0 ? "up" : n < 0 ? "down" : "");

export default function DailySlider({ data }) {
  const agents = data?.agents || [];
  const days = [...(data?.days || [])].sort((a, b) => (a.key < b.key ? -1 : 1)); // eskiden yeniye
  if (!days.length) return null;

  return (
    <div className="day-slider" role="list">
      {days.map((d, i) => {
        const hodlProfit = d.hodl != null ? d.hodl - START : null;
        return (
          <div className="day-card" role="listitem" key={d.key}>
            <div className="day-card-head">
              <span className="day-num">{i + 1}. gün</span>
              <span className="day-date">{d.label}</span>
            </div>
            <ul className="day-rows">
              {agents.map((a, j) => {
                const eq = d.agents[a.agent];
                const profit = eq != null ? eq - START : null;
                return (
                  <li key={a.agent}>
                    <span className="dot" style={{ background: colorFor(a.agent, j) }} />
                    <span className="dc-name">{a.name}</span>
                    <span className={`dc-val ${cls(profit)}`}>{signed(profit)}</span>
                  </li>
                );
              })}
            </ul>
            <div className="day-hodl">
              <span className="dc-name">Bekleyen (HODL)</span>
              <span className={`dc-val ${cls(hodlProfit)}`}>{signed(hodlProfit)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
