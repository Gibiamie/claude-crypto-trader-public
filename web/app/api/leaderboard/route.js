import { standings } from "@/lib/journal";

export const dynamic = "force-dynamic";

/** Public okuma endpoint'i — auth yok, kasten. Veri zaten herkese açık. */
export async function GET() {
  const rows = await standings();
  return Response.json(
    {
      updated_at: new Date().toISOString(),
      agents: rows.map((r) => ({
        agent: r._id,
        label: r.label,
        tick: r.tick,
        ts: r.ts,
        equity: r.equity,
        hodl: r.hodl,
        pnl_pct: r.equity ? +((r.equity / 10000 - 1) * 100).toFixed(2) : null,
        vs_hodl_pct: r.equity && r.hodl ? +((r.equity / r.hodl - 1) * 100).toFixed(2) : null,
        trades: r.trades ?? 0,
        fees_paid: r.fees_paid ?? 0,
        gaps: r.gaps ?? 0,
      })),
    },
    { headers: { "Cache-Control": "public, max-age=30" } },
  );
}
