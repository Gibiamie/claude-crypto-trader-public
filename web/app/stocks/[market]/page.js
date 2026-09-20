import { notFound } from "next/navigation";
import EquityChart from "../../equity-chart";
import { stockDashboard } from "@/lib/stocks";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const pct = (n) => n == null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

function money(n, currency) {
  if (n == null) return "—";
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(n);
}

export default async function StockMarketPage({ params }) {
  const { market } = await params;
  if (!["us", "bist"].includes(market)) notFound();

  const data = await stockDashboard(market);
  if (!data) notFound();

  if (!data.standings.length) {
    return (
      <>
        <div className="card intro">
          <h1 className="market-title">{data.name}</h1>
          <p><strong>{data.experiment_id}</strong> hazır, ancak henüz ilk paper tick çalışmadı.</p>
          <p style={{ marginBottom: 0 }}>
            Bu sistem Midas hesabınıza emir göndermez. İlk aşama yalnız paper simulation.
          </p>
        </div>
        <div className="empty">
          GitHub Actions&apos;ta ilgili workflow&apos;u manuel çalıştırınca ilk veri burada görünecek.
        </div>
      </>
    );
  }

  return (
    <>
      <div className="card intro">
        <h1 className="market-title">{data.name}</h1>
        <p>
          Üç risk karakteri aynı hisse adaylarını ve aynı teknik snapshot&apos;ı görür.
          Başlangıç sermayesi <strong>{money(data.start_cash, data.currency)}</strong>.
        </p>
        <p>
          Benchmark: <strong>{data.benchmark}</strong> · Aktif deney: <strong>{data.experiment_id}</strong>
        </p>
        <p style={{ marginBottom: 0 }}>
          <strong>Paper-only:</strong> Midas hesabına otomatik emir gönderilmez.
          Veri kaynağı: {data.data_source}.
        </p>
      </div>

      <h2>Portföy yarışı</h2>
      <EquityChart data={data.curves} benchmarkLabel={data.benchmark} />

      <h2>Sıralama</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Karakter</th>
              <th className="num">Portföy</th>
              <th className="num">P/L</th>
              <th className="num">Benchmark&apos;a göre</th>
              <th className="num">Nakit</th>
              <th className="num">İşlem</th>
              <th className="num">Sim. sürtünme</th>
            </tr>
          </thead>
          <tbody>
            {data.standings.map((a, i) => (
              <tr key={a.id}>
                <td className="rank">{i + 1}</td>
                <td>
                  <strong>{a.name}</strong>
                  <div className="row-sub">
                    min nakit %{Math.round((a.risk_profile?.min_cash_pct || 0) * 100)}
                    {" · "}max pozisyon %{Math.round((a.risk_profile?.max_position_pct || 0) * 100)}
                  </div>
                </td>
                <td className="num">{money(a.equity, data.currency)}</td>
                <td className={`num ${a.pnl_pct >= 0 ? "up" : "down"}`}>{pct(a.pnl_pct)}</td>
                <td className={`num ${a.vs_benchmark_pct >= 0 ? "up" : "down"}`}>
                  {pct(a.vs_benchmark_pct)}
                </td>
                <td className="num">{money(a.cash, data.currency)}</td>
                <td className="num">{a.trades}</td>
                <td className="num">{money(a.friction_paid, data.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Bu tick&apos;in radarı</h2>
      <p className="section-note">
        Radar tüm başlangıç evrenini deterministik olarak tarar; AI yalnız aşağıdaki adayları
        ve mevcut pozisyonları değerlendirebilir.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Hisse</th>
              <th className="num">Fiyat</th>
              <th className="num">5 bar</th>
              <th className="num">20 bar</th>
              <th className="num">Göreli 20</th>
              <th className="num">RSI14</th>
              <th className="num">Hacim oranı</th>
              <th className="num">Skor</th>
            </tr>
          </thead>
          <tbody>
            {data.candidates.map((c) => (
              <tr key={c.symbol}>
                <td><strong>{c.symbol.replace(".IS", "")}</strong></td>
                <td className="num">{c.last}</td>
                <td className="num">{pct(c.change_5_pct)}</td>
                <td className="num">{pct(c.change_20_pct)}</td>
                <td className="num">{pct(c.rel_20_pct)}</td>
                <td className="num">{c.rsi14}</td>
                <td className="num">{c.volume_ratio}</td>
                <td className="num">{c.score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Son AI kararları</h2>
      <div className="stock-decisions">
        {data.recent.map((r) => (
          <div className="card" key={r.agent}>
            <div className="decision-head">
              <strong>{r.name}</strong>
              <span className="tick">tick {r.tick}</span>
              {r.repaired && <span className="badge">JSON repair</span>}
              {r.gap && <span className="badge gap">gap</span>}
            </div>
            {r.error && <p className="reason down">{r.error}</p>}
            {(r.orders || []).length === 0 ? (
              <p className="reason">İşlem yok.</p>
            ) : (
              <ul className="order-list">
                {r.orders.map((o) => (
                  <li key={o.symbol}>
                    <span className={`action ${o.action}`}>{o.action}</span>
                    <strong>{o.symbol.replace(".IS", "")}</strong>
                    <span className="num">{money(o.notional, data.currency)}</span>
                    <span className="row-sub">{o.reason}</span>
                  </li>
                ))}
              </ul>
            )}
            {r.thesis && <p className="thesis">{r.thesis}</p>}
          </div>
        ))}
      </div>
    </>
  );
}
