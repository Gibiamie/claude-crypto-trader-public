import { readdir, readFile } from "fs/promises";
import path from "path";

// Bot journal/<agent>.jsonl dosyalarına yazar; site bunları okur. Mongo yok.
// Varsayılan: repo kökündeki journal/ (web'in bir üstü). JOURNAL_DIR ile taşınır.
const JOURNAL_DIR = process.env.JOURNAL_DIR
  ? path.resolve(process.env.JOURNAL_DIR)
  : path.resolve(process.cwd(), "..", "journal");

const START_CASH = 10000;

/** Tüm journal satırları, tick artan sırada (agent'lar birlikte). */
async function readAll() {
  let files;
  try {
    files = await readdir(JOURNAL_DIR);
  } catch {
    return []; // journal henüz yok — ilk tick'ten önce
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
        /* bozuk satırı atla */
      }
    }
  }
  rows.sort((a, b) => (a.tick ?? 0) - (b.tick ?? 0));
  return rows;
}

const LATEST_FIELDS = [
  "label", "name", "tagline", "persona", "model", "effort",
  "tick", "ts", "equity", "hodl", "cash", "positions", "prices",
  "trades", "fees_paid", "thesis", "gap",
];

/** Her agent için son tick + biriken maliyet/token — leaderboard kaynağı. */
export async function standings() {
  const rows = await readAll();
  const byAgent = new Map();

  for (const r of rows) {
    let g = byAgent.get(r.agent);
    if (!g) {
      g = { _id: r.agent, ai_cost: 0, tok_in: 0, tok_out: 0,
            tok_cache_w: 0, tok_cache_r: 0, gaps: 0 };
      byAgent.set(r.agent, g);
    }
    const u = r.usage || {};
    g.ai_cost += u.cost_usd || 0;   // yapay zeka gideri her saat birikir
    g.tok_in += u.input || 0;
    g.tok_out += u.output || 0;
    g.tok_cache_w += u.cache_create || 0;
    g.tok_cache_r += u.cache_read || 0;
    if (r.gap) g.gaps += 1;
    // Son tick'in skalerleri (rows tick artan sırada; tanımlıysa üzerine yaz —
    // yalın market-gap satırı son iyi equity'yi silmesin).
    for (const k of LATEST_FIELDS) if (r[k] !== undefined) g[k] = r[k];
  }

  const out = [...byAgent.values()];
  // Sıralama net sonuca göre: portföy tek başına yanıltıcı, yapay zeka gideri düşülmemiş.
  for (const g of out) g.net = g.equity != null ? g.equity - START_CASH - g.ai_cost : null;
  out.sort((a, b) => (b.net ?? -Infinity) - (a.net ?? -Infinity));
  return out;
}

/** Agent kimlikleri — son tick'ten okunur, config'e bağımlı değil. */
export async function profiles() {
  const rows = await readAll();
  const byAgent = new Map();
  for (const r of rows) {
    const g = byAgent.get(r.agent) || { _id: r.agent };
    for (const k of ["name", "label", "tagline", "persona", "model", "effort"]) {
      if (r[k] !== undefined) g[k] = r[k];
    }
    byAgent.set(r.agent, g);
  }
  return [...byAgent.values()].sort((a, b) => (a._id < b._id ? -1 : 1));
}

/** Tüm agent'ların zaman içindeki equity eğrisi + HODL çizgisi. */
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

/**
 * Gün gün sonuç — her günün SON tick'indeki equity + HODL.
 * Gün sınırı TR saatiyle (Europe/Istanbul).
 */
export async function dailyResults(tz = "Europe/Istanbul") {
  const rows = await readAll();

  const dayKey = (d) =>
    new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  const dayLabel = (d) =>
    new Intl.DateTimeFormat("tr-TR", { timeZone: tz, day: "numeric", month: "long" }).format(d);

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
    // rows tick artan sırada — aynı (agent, gün) için son yazan günün son tick'i.
    day.agents[r.agent] = r.equity;
    if (r.hodl != null) day.hodl = r.hodl;
  }

  const ORDER = { temkinli: 0, dengeli: 1, risksever: 2 }; // korkak → cesur
  const agentList = [...agents.entries()]
    .map(([agent, name]) => ({ agent, name }))
    .sort((a, b) => (ORDER[a.agent] ?? 99) - (ORDER[b.agent] ?? 99) || (a.name < b.name ? -1 : 1));

  const dayList = [...days.values()].sort((a, b) => (a.key < b.key ? 1 : -1)); // yeni gün üstte

  return { agents: agentList, days: dayList };
}

/** Bir agent'ın son N kararı — gerekçeleriyle (raw ve prices hariç). */
export async function recentDecisions(agent, limit = 40) {
  const rows = await readAll();
  return rows
    .filter((r) => r.agent === agent)
    .sort((a, b) => (b.tick ?? 0) - (a.tick ?? 0))
    .slice(0, limit)
    .map(({ raw, prices, ...rest }) => rest);
}
