import { recentDecisions } from "@/lib/journal";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const fmt = (n, d = 2) =>
  n == null ? "—" : n.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });

export default async function Agent({ params }) {
  const { id } = await params;
  const rows = await recentDecisions(id);

  if (!rows.length) {
    return <div className="empty">Bu agent için kayıt yok.</div>;
  }

  const head = rows[0];
  const title = head.name || head.label || id;

  return (
    <>
      <h2>{title}</h2>
      <div className="card persona-card">
        <div className="persona-head">
          <strong className="persona-name">{title}</strong>
          {head.model && (
            <span className="badge">
              {head.model} · effort {head.effort}
            </span>
          )}
        </div>
        {head.tagline && <p className="persona-tag">{head.tagline}</p>}
        {head.persona ? (
          <>
            <p className="chart-title">Ona verilen talimat</p>
            <pre className="persona-prompt">{head.persona}</pre>
          </>
        ) : null}
      </div>

      <h2>Her saat ne yaptı?</h2>
      <p className="section-note">
        En yeni karar en üstte. Her satırda ne aldı, ne sattı ve{" "}
        <strong>neden</strong> öyle yaptığı yazıyor — kendi cümleleriyle.
      </p>

      {rows.map((r) => (
        <div className="card" key={r.tick}>
          <div className="decision-head">
            <span className="tick">
              tick {r.tick} · {new Date(r.ts).toLocaleString("tr-TR")}
            </span>
            <span className="tick">portföy ${fmt(r.equity)}</span>
            {r.gap && <span className="badge gap">GAP</span>}
          </div>

          {r.gap ? (
            <p className="reason" style={{ color: "var(--down)" }}>
              Model yanıt veremedi — portföye dokunulmadı. Sebep: {r.error || "bilinmiyor"}
            </p>
          ) : (
            <>
              {(r.decisions || []).map((d, i) => (
                <p className="reason" key={i}>
                  <span className={`action ${d.action}`}>{d.action}</span>{" "}
                  <strong>{d.coin}</strong>
                  {d.action !== "HOLD" && d.usd ? ` · $${fmt(d.usd)}` : ""}
                  {d.confidence != null ? (
                    <span style={{ color: "var(--dim)" }}> · güven {d.confidence}</span>
                  ) : null}
                  <br />
                  <span style={{ color: "var(--dim)" }}>{d.reason}</span>
                </p>
              ))}
              {r.thesis && <p className="thesis">{r.thesis}</p>}
            </>
          )}
        </div>
      ))}
    </>
  );
}
