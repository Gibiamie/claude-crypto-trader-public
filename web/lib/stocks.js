import { readdir, readFile } from "fs/promises";
import path from "path";

const ACTIVE = {
  us: "us-v1.1-2026-09-21",
  bist: "bist-v1.1-2026-09-21",
};

const FALLBACK = {
  us: { name: "US Stocks", currency: "USD", start_cash: 10000, benchmark: "SPY" },
  bist: { name: "BIST", currency: "TRY", start_cash: 100000, benchmark: "BIST 100" },
};

async function rowsFor(market) {
  const experiment = ACTIVE[market];
  if (!experiment) return [];
  const dir = path.resolve(process.cwd(), "..", "stock_journal", market);
  let files = [];
  try {
    files = await readdir(dir);
  } catch {
    return [];
  }

  const rows = [];
  for (const file of files) {
    if (!file.endsWith(".jsonl")) continue;
    const text = await readFile(path.join(dir, file), "utf8");
    for (const line of text.split("\n")) {
      if (!line.trim()) continue;
      try {
        const row = JSON.parse(line);
        if (row.experiment_id === experiment) rows.push(row);
      } catch {
        // malformed line excluded
      }
    }
  }
  rows.sort((a, b) => (+new Date(a.ts) || 0) - (+new Date(b.ts) || 0));
  return rows;
}

export async function stockDashboard(market) {
  const rows = await rowsFor(market);
  const fallback = FALLBACK[market];
  if (!fallback) return null;

  if (!rows.length) {
    return {
      market,
      ...fallback,
      experiment_id: ACTIVE[market],
      standings: [],
      curves: { series: [], hodl: [] },
      candidates: [],
      data_source: null,
      latest_ts: null,
      recent: [],
    };
  }

  const byAgent = new Map();
  const curves = new Map();
  const benchmark = [];
  const seenTicks = new Set();

  for (const row of rows) {
    let a = byAgent.get(row.agent);
    if (!a) {
      a = {
        id: row.agent,
        name: row.name || row.agent,
        gaps: 0,
        repairs: 0,
        ai_cost: 0,
      };
      byAgent.set(row.agent, a);
    }

    if (row.gap) a.gaps++;
    if (row.repaired) a.repairs++;
    a.ai_cost += row.usage?.cost_usd || 0;
    Object.assign(a, {
      equity: row.equity,
      cash: row.cash,
      positions: row.positions || {},
      trades: row.trades || 0,
      friction_paid: row.friction_paid || 0,
      benchmark_value: row.benchmark_value,
      thesis: row.thesis,
      tick: row.tick,
      ts: row.ts,
      risk_profile: row.risk_profile,
    });

    if (row.equity != null) {
      let s = curves.get(row.agent);
      if (!s) {
        s = { agent: row.agent, name: row.name || row.agent, points: [] };
        curves.set(row.agent, s);
      }
      const fills = Array.isArray(row.fills) ? row.fills : [];
      s.points.push({
        t: +new Date(row.ts),
        equity: row.equity,
        gap: Boolean(row.gap),
        buy: fills.some((f) => f?.ok && f.side === "BUY"),
        sell: fills.some((f) => f?.ok && f.side === "SELL"),
      });
    }

    if (row.benchmark_value != null && !seenTicks.has(row.tick)) {
      seenTicks.add(row.tick);
      benchmark.push({ t: +new Date(row.ts), value: row.benchmark_value });
    }
  }

  const latest = rows[rows.length - 1];
  const startCash = latest.start_cash ?? fallback.start_cash;
  const standings = [...byAgent.values()].map((a) => ({
    ...a,
    pnl: a.equity != null ? a.equity - startCash : null,
    pnl_pct: a.equity != null ? (a.equity / startCash - 1) * 100 : null,
    vs_benchmark_pct:
      a.equity && a.benchmark_value ? (a.equity / a.benchmark_value - 1) * 100 : null,
  })).sort((a, b) => (b.pnl ?? -Infinity) - (a.pnl ?? -Infinity));

  const latestByAgent = new Map();
  for (const row of rows) latestByAgent.set(row.agent, row);

  return {
    market,
    name: latest.market_name || fallback.name,
    currency: latest.currency || fallback.currency,
    start_cash: startCash,
    experiment_id: latest.experiment_id,
    benchmark: latest.benchmark_name || fallback.benchmark,
    data_source: latest.data_source,
    latest_ts: latest.ts,
    standings,
    curves: { series: [...curves.values()], hodl: benchmark },
    candidates: latest.market_snapshot?.candidates || [],
    recent: [...latestByAgent.values()].map((row) => ({
      agent: row.agent,
      name: row.name,
      tick: row.tick,
      thesis: row.thesis,
      orders: row.orders || [],
      fills: row.fills || [],
      repaired: Boolean(row.repaired),
      gap: Boolean(row.gap),
      error: row.error,
    })),
  };
}
