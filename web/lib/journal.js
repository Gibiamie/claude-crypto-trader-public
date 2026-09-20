import { readdir, readFile } from "fs/promises";
import path from "path";

export const ACTIVE_EXPERIMENT_ID = process.env.EXPERIMENT_ID || "v2-2026-09-20";

const JOURNAL_DIR = process.env.JOURNAL_DIR
  ? path.resolve(process.env.JOURNAL_DIR)
  : path.resolve(process.cwd(), "..", "journal");

const START_CASH = 10000;

async function readRaw() {
  let files;
  try {
    files = await readdir(JOURNAL_DIR);
  } catch {
    return [];
  }

  const rows = [];
  for (const f of files) {
    if (!f.endsWith(".jsonl")) continue;
    const text = await readFile(path.join(JOURNAL_DIR, f), "utf8");
    for (const line of text.split("\n")) {
      const s = line.trim();
      if (!s) continue;
      try {
        rows.push(JSON.parse(s));
      } catch {
        // Bozuk satır performans hesabına girmez.
      }
    }
  }
  rows.sort((a, b) => (a.tick ?? 0) - (b.tick ?? 0));
  return rows;
}

async function readAll() {
  const rows = await readRaw();
  return rows.filter((r) => r.experiment_id === ACTIVE_EXPERIMENT_ID);
}

const LATEST_FIELDS = [
  "label", "name", "tagline", "persona", "model", "effort", "temperature",
  "experiment_id", "schema_version", "strategy_version", "git_sha",
  "tick", "ts", "equity", "hodl", "cash", "positions", "prices",
  "trades", "fees_paid", "realized_pnl", "thesis", "gap",
];

export async function standings() {
  const rows = await readAll();
  const byAgent = new Map();

  for (const r of rows) {
    let g = byAgent.get(r.agent);
    if (!g) {
      g = {
        _id: r.agent,
        ai_cost: 0,
        tok_in: 0,
        tok_out: 0,
        tok_cache_w: 0,
        tok_cache_r: 0,
        gaps: 0,
        repaired: 0,
      };
      byAgent.set(r.agent, g);
    }

    const u = r.usage || {};
    g.ai_cost += u.cost_usd || 0;
    g.tok_in += u.input || 0;
    g.tok_out += u.output || 0;
    g.tok_cache_w += u.cache_create || 0;
    g.tok_cache_r += u.cache_read || 0;
    if (r.gap) g.gaps += 1;
    if (r.repaired) g.repaired += 1;

    for (const k of LATEST_FIELDS) {
      if (r[k] !== undefined) g[k] = r[k];
    }
  }

  const out = [...byAgent.values()];
  for (const g of out) {
    g.net = g.equity != null ? g.equity - START_CASH - g.ai_cost : null;
  }
  out.sort((a, b) => (b.net ?? -Infinity) - (a.net ?? -Infinity));
  return out;
}

export async function profiles() {
  const rows = await readAll();
  const byAgent = new Map();
  for (const r of rows) {
    const g = byAgent.get(r.agent) || { _id: r.agent };
    for (const k of ["name", "label", "tagline", "persona", "model", "effort", "temperature"]) {
      if (r[k] !== undefined) g[k] = r[k];
    }
    byAgent.set(r.agent, g);
  }
  return [...byAgent.values()].sort((a, b) => (a._id < b._id ? -1 : 1));
}

export async function equityCurves() {
  const rows = await readAll();
  const byAgent = new Map();
  const hodl = [];
  const seenHodl = new Set();

  for (const r of rows) {
    const t = +new Date(r.ts);
    if (r.equity != null) {
      let s = byAgent.get(r.agent);
      if (!s) {
        s = { agent: r.agent, name: r.name || r.label || r.agent, points: [] };
        byAgent.set(r.agent, s);
      }
      const fills = Array.isArray(r.fills) ? r.fills : [];
      s.points.push({
        t,
        equity: r.equity,
        gap: Boolean(r.gap),
        buy: fills.some((f) => f?.ok && f.side === "BUY"),
        sell: fills.some((f) => f?.ok && f.side === "SELL"),
      });
    }

    if (r.hodl != null && !seenHodl.has(r.tick)) {
      seenHodl.add(r.tick);
      hodl.push({ t, value: r.hodl });
    }
  }

  const series = [...byAgent.values()].sort((a, b) => (a.agent < b.agent ? -1 : 1));
  return { series, hodl };
}

export async function dailyResults(tz = "Europe/Istanbul") {
  const rows = await readAll();

  const dayKey = (d) =>
    new Intl.DateTimeFormat("en-CA", {
      timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit",
    }).format(d);
  const dayLabel = (d) =>
    new Intl.DateTimeFormat("tr-TR", {
      timeZone: tz, day: "numeric", month: "long",
    }).format(d);

  const agents = new Map();
  const days = new Map();

  for (const r of rows) {
    if (r.equity == null) continue;
    const d = new Date(r.ts);
    const key = dayKey(d);
    agents.set(r.agent, r.name || r.label || r.agent);
    let day = days.get(key);
    if (!day) {
      day = { key, label: dayLabel(d), hodl: null, agents: {} };
      days.set(key, day);
    }
    day.agents[r.agent] = r.equity;
    if (r.hodl != null) day.hodl = r.hodl;
  }

  const ORDER = { temkinli: 0, dengeli: 1, risksever: 2 };
  const agentList = [...agents.entries()]
    .map(([agent, name]) => ({ agent, name }))
    .sort((a, b) => (ORDER[a.agent] ?? 99) - (ORDER[b.agent] ?? 99) || (a.name < b.name ? -1 : 1));

  const dayList = [...days.values()].sort((a, b) => (a.key < b.key ? 1 : -1));
  return { agents: agentList, days: dayList };
}

export async function recentDecisions(agent, limit = 40) {
  const rows = await readAll();
  return rows
    .filter((r) => r.agent === agent)
    .sort((a, b) => (b.tick ?? 0) - (a.tick ?? 0))
    .slice(0, limit)
    .map(({ raw, market_snapshot, portfolio_state, ...rest }) => rest);
}

export async function experimentStatus() {
  const [all, active] = await Promise.all([readRaw(), readAll()]);
  if (!active.length) {
    return {
      experiment_id: ACTIVE_EXPERIMENT_ID,
      runs: 0,
      expected_runs: 0,
      coverage_pct: null,
      gaps: 0,
      repaired: 0,
      legacy_rows: all.filter((r) => r.experiment_id !== ACTIVE_EXPERIMENT_ID).length,
      first_ts: null,
      last_ts: null,
    };
  }

  const firstMs = Math.min(...active.map((r) => +new Date(r.ts)).filter(Number.isFinite));
  const lastMs = Math.max(...active.map((r) => +new Date(r.ts)).filter(Number.isFinite));
  const ticks = new Set(active.map((r) => r.tick).filter((x) => Number.isInteger(x)));
  const expected = Math.max(1, Math.floor((lastMs - firstMs) / 3600000) + 1);
  const coverage = Math.min(100, (ticks.size / expected) * 100);

  return {
    experiment_id: ACTIVE_EXPERIMENT_ID,
    runs: ticks.size,
    expected_runs: expected,
    coverage_pct: Number.isFinite(coverage) ? coverage : null,
    gaps: active.filter((r) => r.gap).length,
    repaired: active.filter((r) => r.repaired).length,
    legacy_rows: all.filter((r) => r.experiment_id !== ACTIVE_EXPERIMENT_ID).length,
    first_ts: new Date(firstMs).toISOString(),
    last_ts: new Date(lastMs).toISOString(),
  };
}
