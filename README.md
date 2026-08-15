# claude-crypto-trader

Three AI characters each get $10,000 in fake money. Every hour they look at the
market and decide on their own whether to buy or sell crypto. All three use the
same model (Claude Opus) and see the same data. The only difference is their risk
character: one is cautious, one is balanced, one is aggressive.

The question: do they do any better than just buying and holding (HODL)?

No real money. No wallet, private key, or KYC. Prices come from Hyperliquid's
public `/info` endpoint. Every trade pays a 0.07% fee and 0.05% slippage, so the
results stay close to real. Each tick is written to `journal/<character>.jsonl`,
and the dashboard reads those files. No database.

The dashboard UI and the character prompts are in Turkish.

## How it works

```
tick.py (hourly)
  ├─ hl.py       Hyperliquid public /info → live price + closed candles
  ├─ prompt.py   market + portfolio → prompt (same for all but the persona)
  ├─ agents.py   claude -p --model opus --effort max  (no tools, JSON in/out)
  ├─ broker.py   paper broker: fee + slippage, spot, no leverage + HODL
  └─ journal/<character>.jsonl   ← the single source of truth (append-only)

web/  Next.js dashboard that reads the journal files
```

## Requirements

- Python 3.11+ (standard library only, nothing to install)
- [Claude Code](https://claude.com/claude-code) installed and logged in (the
  `claude` command must run from your PATH). The model is called through it, so
  you do not need a separate API key.

## Quick start

```bash
git clone <repo-url> claude-crypto-trader
cd claude-crypto-trader

python3 tick.py --dry-run          # print the prompt, no model call (free, try this first)
python3 tick.py                    # one tick for all characters
python3 tick.py --only temkinli    # a single character
```

Each run of `tick.py` advances one hour: it fetches prices, asks each character
for a decision, updates the portfolios, and writes to `journal/`. Put it on an
hourly cron and the experiment runs itself (below).

No environment variables are needed. The only requirement is that `claude` is
logged in.

## Dashboard (optional)

Leaderboard, a chart over time, and daily results. It reads the `journal/` files
directly, on the same machine, with no database.

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

If the journal lives somewhere else, point to it:
`JOURNAL_DIR=/absolute/path/journal npm run dev`. The default is `../journal`
next to the repo root.

## Cron (hourly)

```cron
PATH=/usr/local/bin:/usr/bin:/bin
0 * * * * cd /path/claude-crypto-trader && flock -n /tmp/cct.lock python3 -u tick.py >> tick.log 2>&1
```

- `flock -n` stops overlapping runs. A tick can take a few minutes on a timeout.
- The `PATH` line matters. Cron's default PATH may not include `claude`; add the
  directory from `which claude`.
- `python3 -u` turns off buffering, otherwise the cron log fills only after the
  process ends.

## Design decisions

**The fill price comes from `allMids`, not the candle close.** The last candle
Hyperliquid returns is always still open. If you fill at its close you are seeing
the future, and every result turns fake. The model is also shown closed candles
only.

**Spot pair names are in `@index` form.** UBTC/USDC is `@142`, UETH/USDC is
`@151`, HYPE/USDC is `@107`. Only PURR/USDC has a readable name. A candle query
with the readable name comes back empty. `config.ASSETS` holds these. To check
them: `curl -s -X POST https://api.hyperliquid.xyz/info -d '{"type":"spotMeta"}'`

**The fee simulation cannot be turned off.** Taker fee 0.07% plus 0.05% slippage.
Turn it off and an aggressive strategy looks better than it is. The prompt tells
the model this directly.

**On an error the portfolio holds, it is not skipped.** If the model hits a
limit, the network drops, or the JSON is broken, the portfolio stays put and a
`gap: true` line goes into the journal. The chart shows a hole. Showing it beats
hiding it.

**No short selling and no leverage.** Blocked at the broker level. If the model
says SELL on a coin it does not hold, the order is rejected.

## Changing the characters

The `AGENTS` list in `config.py`. The only thing that changes is the persona, the
risk character. Model, effort, and the data shown are the same for all three,
which is what lets the leaderboard measure how much risk appetite alone changes
the outcome. Do not touch the `id` field, it is the key for the journal file.
`name` can change freely.

## Cost warning

Every tick makes one model call per character (`opus --effort max`). Hourly,
three characters, that is not a small amount of usage. Check your quota and
spending limit before going live. To try it out, run `--dry-run` first, then
`--only` for a single character.

This is an experiment, not financial advice.
