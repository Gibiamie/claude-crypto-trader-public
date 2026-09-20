import Donut from "./donut";
import EquityChart from "./equity-chart";
import DailySlider from "./daily-slider";
import {
  dailyResults,
  equityCurves,
  experimentStatus,
  profiles,
  standings,
} from "@/lib/journal";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const money = (n) =>
  n == null ? "—" : "$" + n.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const signed = (n) =>
  n == null
    ? "—"
    : (n > 0 ? "+" : n < 0 ? "−" : "") +
      "$" +
      Math.abs(n).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const tokens = (n) => {
  if (n == null) return "—";
  const tr = (x, d = 0) => x.toLocaleString("tr-TR", { maximumFractionDigits: d });
  if (n >= 1e6) return tr(n / 1e6, 1) + " milyon";
  if (n >= 1e3) return tr(Math.round(n / 1e3)) + " bin";
  return tr(n);
};

const pct = (n) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(2)}%`);
const cls = (n) => (n == null ? "" : n > 0 ? "up" : n < 0 ? "down" : "");

function slicesOf(row) {
  const out = [];
  const pos = row.positions || {};
  const px = row.prices || {};
  for (const [coin, qty] of Object.entries(pos)) {
    if (px[coin]) out.push({ label: coin, value: qty * px[coin] });
  }
  out.sort((a, b) => b.value - a.value);
  out.push({ label: "Nakit", value: row.cash || 0 });
  return out;
}

export default async function Home() {
  const [rows, people, curves, daily, status] = await Promise.all([
    standings(),
    profiles(),
    equityCurves(),
    dailyResults(),
    experimentStatus(),
  ]);

  if (!rows.length) {
    return (
      <div className="empty">
        <strong>{status.experiment_id}</strong> henüz ilk geçerli tick&apos;ini üretmedi.
        Eski Phase 0 kayıtları ({status.legacy_rows} satır) korunuyor ancak V2 sonuçlarına dahil edilmiyor.
      </div>
    );
  }

  const hodl = rows[0]?.hodl ?? null;
  const byId = Object.fromEntries(rows.map((r) => [r._id, r]));

  return (
    <>
      <div className="card intro">
        <p>
          Üç yapay zeka karakterine <strong>10.000 dolar sanal para</strong> verdik.
          Saatlik çalıştırılan simülasyonda aynı piyasa verisini ve aynı modeli görüyorlar.
          Tek kontrollü fark: <strong>risk karakterleri.</strong>
        </p>
        <p style={{ marginBottom: 0 }}>
          Aktif deney: <strong>{status.experiment_id}</strong>. Phase 0 verileri arşiv amaçlı korunur,
          bu leaderboard&apos;a karışmaz.
        </p>
      </div>

      <div className="card">
        <h3>Deney sağlığı</h3>
        <p style={{ marginBottom: 0 }}>
          Çalışma sayısı: <strong>{status.runs}</strong>
          {" · "}Planlanan saate göre kapsama: <strong>{status.coverage_pct == null ? "—" : `${status.coverage_pct.toFixed(1)}%`}</strong>
          {" · "}Cevap/veri boşluğu: <strong>{status.gaps}</strong>
          {" · "}JSON repair: <strong>{status.repaired}</strong>
        </p>
      </div>

      <h2>Zaman içinde kim önde?</h2>
      <p className="section-note">
        Her karakterin stateful portföy değeri saat saat izlenir. Kesikli çizgi:
        <strong> V2 başlangıcında eşit dolar tutarıyla alınan BTC + ETH + HYPE buy-and-hold benchmarkı.</strong>
        Üçgenler o tick&apos;te gerçekleşen alım veya satımı gösterir. Cevap/veri boşluklarında çizgi kesilir.
      </p>
      <EquityChart data={curves} />

      <h2>Gün gün sonuçlar</h2>
      <p className="section-note">
        Her kart o günün son geçerli portföy değerini gösterir. Herkes V2&apos;ye 10.000 dolarla başladı.
      </p>
      <DailySlider data={daily} />

      <h2>Sıralama</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Karakter</th>
              <th className="num">Şu anki parası</th>
              <th className="num">Kâr / Zarar</th>
              <th className="num">HODL&apos;a göre</th>
              <th className="num">Kaç işlem yaptı</th>
              <th className="num">Ödediği komisyon</th>
              <th className="num">Yapay zeka gideri</th>
              <th className="num">Net sonuç</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const pnl = r.equity ? (r.equity / 10000 - 1) * 100 : null;
              const vs = r.equity && r.hodl ? (r.equity / r.hodl - 1) * 100 : null;
              const net = r.equity != null ? r.equity - 10000 - (r.ai_cost || 0) : null;
              return (
                <tr key={r._id}>
                  <td className="rank">{i + 1}</td>
                  <td>
                    <a className="agent-link" href={`/agent/${r._id}`}>
                      <strong>{r.name || r._id}</strong>
                    </a>
                    {r.gaps > 0 && (
                      <>
                        {" "}
                        <span className="badge gap" title="Modelin veya piyasa verisinin cevap veremediği tick sayısı">
                          {r.gaps} gap
                        </span>
                      </>
                    )}
                    {r.tagline && <div className="row-sub">{r.tagline}</div>}
                  </td>
                  <td className="num">{money(r.equity)}</td>
                  <td className={`num ${cls(pnl)}`}>{pct(pnl)}</td>
                  <td className={`num ${cls(vs)}`}>{pct(vs)}</td>
                  <td className="num">{r.trades ?? 0}</td>
                  <td className="num">{money(r.fees_paid)}</td>
                  <td className="num">{signed(-(r.ai_cost || 0))}</td>
                  <td className={`num ${cls(net)}`}>
                    <strong>{signed(net)}</strong>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="card explain">
        <h3>Benchmark ve maliyetler</h3>
        <dl>
          <dt>HODL&apos;a göre</dt>
          <dd>
            V2&apos;nin ilk tick&apos;inde 10.000 dolar üçe bölünüp BTC, ETH ve HYPE alınmış
            ve sonrasında hiç işlem yapılmamış kabul edilir. Girişte aynı fee ve slippage uygulanır.
            Bugünkü benchmark değeri <strong>{money(hodl)}</strong>.
          </dd>

          <dt>Ödediği komisyon</dt>
          <dd>
            Paper broker her gerçekleşen alım/satımda %0,07 taker fee ve %0,05 slippage uygular.
          </dd>

          <dt>Yapay zeka gideri</dt>
          <dd>
            Model sağlayıcısının bu deney için raporladığı kullanım maliyetidir.
            NVIDIA NIM ücretsiz kullanımında bu değer şu anda 0 dolar olabilir; token sayıları ayrıca tutulur.
          </dd>

          <dt>Net sonuç</dt>
          <dd>
            Portföy değeri − 10.000 dolar başlangıç sermayesi − raporlanan AI maliyeti.
          </dd>
        </dl>
      </div>

      <h2>Karakterler ve portföyleri</h2>
      <p className="section-note">
        Üç karakter aynı model, aynı temperature ve aynı market snapshot&apos;ını alır.
        Aşağıda yalnız persona talimatları farklıdır.
      </p>

      {people.map((p) => {
        const row = byId[p._id];
        return (
          <div className="card persona-card" key={p._id}>
            <div className="persona-head">
              <strong className="persona-name">{p.name || p._id}</strong>
              <a className="agent-link persona-more" href={`/agent/${p._id}`}>
                kararlarını gör →
              </a>
            </div>
            {p.tagline && <p className="persona-tag">{p.tagline}</p>}

            {row && (
              <>
                <p className="chart-title">Parasını nereye koydu?</p>
                <Donut slices={slicesOf(row)} total={row.equity} />

                <p className="chart-title">Model kullanımı</p>
                <ul className="cost-list">
                  <li>
                    <span>Harcanan token</span>
                    <span className="num">
                      {tokens(
                        (row.tok_in || 0) +
                        (row.tok_out || 0) +
                        (row.tok_cache_w || 0) +
                        (row.tok_cache_r || 0),
                      )}
                    </span>
                  </li>
                  <li>
                    <span>Raporlanan model maliyeti</span>
                    <span className="num">{money(row.ai_cost || 0)}</span>
                  </li>
                  <li>
                    <span>Temperature</span>
                    <span className="num">{row.temperature ?? "—"}</span>
                  </li>
                </ul>
              </>
            )}

            {p.persona && (
              <>
                <p className="chart-title">Ona verilen persona talimatı</p>
                <pre className="persona-prompt">{p.persona}</pre>
              </>
            )}
          </div>
        );
      })}
    </>
  );
}
