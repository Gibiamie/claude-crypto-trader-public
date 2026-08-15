import Donut from "./donut";
import EquityChart from "./equity-chart";
import DailySlider from "./daily-slider";
import { dailyResults, equityCurves, profiles, standings } from "@/lib/journal";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const money = (n) =>
  n == null ? "—" : "$" + n.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** İşaretli para: +$12,30 / −$4,50 — eksi değer "$-4.50" gibi görünmesin. */
const signed = (n) =>
  n == null
    ? "—"
    : (n > 0 ? "+" : n < 0 ? "−" : "") +
      "$" +
      Math.abs(n).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "18B" gibi kısaltma yerine açık yaz — "B" milyar sanılabiliyor. */
const tokens = (n) => {
  if (n == null) return "—";
  const tr = (x, d = 0) => x.toLocaleString("tr-TR", { maximumFractionDigits: d });
  if (n >= 1e6) return tr(n / 1e6, 1) + " milyon";
  if (n >= 1e3) return tr(Math.round(n / 1e3)) + " bin";
  return tr(n);
};

const pct = (n) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(2)}%`);
const cls = (n) => (n == null ? "" : n > 0 ? "up" : n < 0 ? "down" : "");

/** Bir agent'ın portföyünü halka grafiğe uygun dilimlere çevirir. */
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
  const [rows, people, curves, daily] = await Promise.all([
    standings(),
    profiles(),
    equityCurves(),
    dailyResults(),
  ]);

  if (!rows.length) {
    return (
      <div className="empty">
        Henüz veri yok. İlk saat çalıştığında sonuçlar burada görünecek.
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
          Her saat başı piyasaya bakıp <strong>kendi başlarına</strong> alım satım
          kararı veriyorlar. Üçü de aynı yapay zekayı kullanıyor ve aynı verileri
          görüyor. Tek fark: <strong>karakterleri.</strong> Biri korkak, biri
          dengeli, biri cesur.
        </p>
        <p style={{ marginBottom: 0 }}>
          Amaç şunu görmek: <strong>karakter, sonucu ne kadar değiştiriyor?</strong>
        </p>
      </div>

      <h2>Zaman içinde kim önde?</h2>
      <p className="section-note">
        Her karakterin parası saat saat nasıl değişti. Kesikli çizgi:{" "}
        <strong>hiç dokunmadan bekleyen</strong> (HODL). Üçgenler o saat{" "}
        <strong>alım</strong> (yeşil) ya da <strong>satım</strong> (kırmızı)
        yaptığı an — çok üçgen, çok işlem demek.
      </p>
      <EquityChart data={curves} />

      <h2>Gün gün sonuçlar</h2>
      <p className="section-note">
        Her kart bir gün — <strong>yana kaydırarak</strong> eskiden yeniye gezin.
        Rakamlar o günün sonundaki <strong>toplam kâr/zarar</strong> (herkes
        10.000 dolarla başladı). Altta, hiç dokunmadan bekleyenin (HODL) durumu.
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
              <th className="num">Alıp bekleyene göre</th>
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
              // Net = alım satımdan kazanılan - yapay zekanın kendi gideri.
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
                        <span className="badge gap" title="Yapay zekanın cevap veremediği saat sayısı">
                          {r.gaps} saat cevap yok
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
                  <td className="num down">{signed(-(r.ai_cost || 0))}</td>
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
        <h3>Tablodaki sözler ne demek?</h3>
        <dl>
          <dt>Şu anki parası</dt>
          <dd>
            Elindeki nakit + sahip olduğu coinlerin bugünkü değeri. Herkes 10.000
            dolarla başladı.
          </dd>

          <dt>Alıp bekleyene göre</dt>
          <dd>
            En başta parayı üçe bölüp BTC, ETH ve HYPE alsaydık ve bir daha hiç
            dokunmasaydık, bugün <strong>{money(hodl)}</strong> olurdu. Bu sütun,
            karakterin ondan ne kadar iyi ya da kötü olduğunu gösteriyor.{" "}
            <strong>Artı ise</strong> alım satım yapmak işe yaramış,{" "}
            <strong>eksi ise</strong> hiç uğraşmadan beklemek daha iyiymiş demek.
          </dd>

          <dt>Ödediği komisyon</dt>
          <dd>
            Borsaya ödenen işlem ücreti. Her alım satımda tutarın %0,07&apos;si
            kesiliyor, üstüne %0,05 fiyat kayması ekleniyor. Çok işlem yapan çok
            öder — bu yüzden gereksiz alım satım kazancı yer.{" "}
            <em>Yapay zekanın kendi maliyeti bu tabloya dahil değil.</em>
          </dd>

          <dt>Kaç işlem yaptı</dt>
          <dd>Şimdiye kadar kaç kez alım veya satım yaptığı.</dd>

          <dt>Yapay zeka gideri</dt>
          <dd>
            Her saat başı her karakter yapay zekaya soru soruyor ve bu bedava
            değil. Bu sütun, o karakterin bugüne kadar harcadığı yapay zeka
            parasını gösteriyor. Kaç kelime (token) harcadığı aşağıdaki
            kartlarda yazıyor.
            <br />
            <em>
              Not: bu rakam, kullanılan yapay zeka aylık abonelikle çalıştığı
              için cebimizden tek tek çıkmıyor. &quot;Bu kadar token, liste
              fiyatından şu kadar tutardı&quot; hesabı. Yine de gerçek maliyeti
              görmek için doğru ölçü bu.
            </em>
          </dd>

          <dt>Net sonuç</dt>
          <dd>
            <strong>En önemli sayı bu.</strong> Alım satımdan kazandığı para{" "}
            <em>eksi</em> yapay zeka gideri. Çünkü bir bot 50 dolar kazanıp 200
            dolar yapay zeka gideri yapıyorsa aslında para kaybediyordur. Burada
            kâr diyebilmek için, yapay zekanın kendi masrafını da çıkarması gerekiyor.
          </dd>
        </dl>
      </div>

      <h2>Karakterler ve portföyleri</h2>
      <p className="section-note">
        Aşağıda her karaktere verilen talimatın <strong>tamamı</strong> yazıyor.
        Gizli bir şey yok — üçü de bu metni okuyup karar veriyor.
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

                <p className="chart-title">Yapay zeka masrafı</p>
                <ul className="cost-list">
                  <li>
                    <span>Harcanan kelime (token)</span>
                    <span className="num">
                      {tokens(
                        (row.tok_in || 0) + (row.tok_out || 0) +
                        (row.tok_cache_w || 0) + (row.tok_cache_r || 0),
                      )}
                    </span>
                  </li>
                  <li>
                    <span>Bunun parası</span>
                    <span className="num down">{signed(-(row.ai_cost || 0))}</span>
                  </li>
                  <li>
                    <span>Saat başına ortalama</span>
                    <span className="num">
                      {money((row.ai_cost || 0) / ((row.tick ?? 0) + 1))}
                    </span>
                  </li>
                </ul>
              </>
            )}

            {p.persona && (
              <>
                <p className="chart-title">Ona verilen talimat</p>
                <pre className="persona-prompt">{p.persona}</pre>
              </>
            )}
          </div>
        );
      })}
    </>
  );
}
