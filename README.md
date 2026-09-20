# claude-crypto-trader — V2

Three AI risk personas paper-trade BTC, ETH and HYPE with the same market data and the same model settings.

The experiment asks one narrow question:

> How much does risk persona change portfolio behaviour and performance when model and inputs are held constant?

No real money, wallet, private key or KYC is used.

## Active experiment

`v2.1-2026-09-20`

Phase 0 / V1 rows are intentionally kept in `journal/*.jsonl` for audit history, but the dashboard excludes them from V2 performance calculations.

## V2 architecture

```text
GitHub Actions (hourly)
  ├─ Hyperliquid public /info
  ├─ closed 1h candles only
  ├─ NVIDIA NIM: nvidia/nemotron-3.5-lightning-30b-a3b
  ├─ temperature = 0
  ├─ strict JSON validation + one repair retry
  ├─ stateful paper broker
  │    ├─ spot only
  │    ├─ no leverage / no short
  │    ├─ 0.07% taker fee
  │    └─ 0.05% slippage
  ├─ journal/<agent>.jsonl
  └─ state/v2.1-2026-09-20/*.json  ← persisted back to GitHub

Vercel / Next.js
  └─ reads active experiment rows and renders the dashboard
```

## Why V2 exists

The original GitHub Actions workflow persisted only `journal/*.jsonl`, while the paper broker stored portfolio and HODL state under ignored `state/`.

Because GitHub-hosted runners are ephemeral, every run effectively started from a fresh $10,000 portfolio and recreated the HODL benchmark.

V2 fixes this by persisting both journal and state, while also storing a full `portfolio_state` snapshot in every journal row as a recovery path. The first live V2 validation exposed a first-entry repair edge case; V2.1 starts clean and enforces at least one BUY until an agent has established its first position.

## Execution rules

All agents see the same market snapshot.

The only intended experimental variable is persona:

- **Stop** — cautious
- **Endeks** — balanced
- **Boğa** — aggressive

For each tick:

1. SELL orders execute first.
2. BUY requests are evaluated together.
3. If total requested BUY notional exceeds available cash, every BUY is scaled proportionally.
4. JSON order therefore cannot decide which asset receives the remaining cash.
5. Every agent decision must contain exactly one decision for BTC, ETH and HYPE.

## Benchmark

The benchmark is explicitly:

**equal-dollar BTC + ETH + HYPE buy-and-hold from V2 t0**, including the same entry fee and slippage assumptions.

It is not a generic crypto benchmark.

## Data recorded per V2 tick

Each row includes:

- `experiment_id`
- schema and strategy version
- Git commit SHA
- model and temperature
- full market snapshot shown to the model
- decisions and confidence
- fills
- portfolio state
- equity / cash / positions
- fee total and realized P/L
- HODL value
- gap / repair flags

## Run locally

Python 3.11+; standard library only.

```bash
export NVIDIA_API_KEY="..."
python3 -m unittest discover -s tests -v
python3 tick.py --dry-run
python3 tick.py
```

## Dashboard

```bash
cd web
npm install
npm run dev
```

The public endpoint is:

```text
/api/leaderboard
```

It returns only the active experiment.

## Scheduling

`.github/workflows/tick.yml` runs at minute 17 of each hour. GitHub Actions schedules can still be delayed; the dashboard reports run coverage and gaps.

This is an experiment, not financial advice.


---

## Multi-market stock experiments

The same repository now contains two additional **paper-only** market experiments:

- **US Stocks** — `/stocks/us`
- **BIST** — `/stocks/bist`

They do not send orders to Midas or any other live brokerage account.

### Stock engine

```text
starter universe
    ↓
deterministic technical screener
    ↓
top 8 candidates
    ↓
Stop / Endeks / Boğa
    ↓
risk-budgeted paper execution
    ↓
stock_journal/<market>/*.jsonl
stock_state/<market>/<experiment>/*.json
    ↓
web dashboard
```

US and BIST use separate experiment IDs, state directories, journals, starting cash and benchmarks.

| Market | Experiment | Start cash | Benchmark |
|---|---|---:|---|
| US | `us-v1-2026-09-20` | $10,000 | SPY |
| BIST | `bist-v1-2026-09-20` | ₺100,000 | BIST 100 |

Starting cash is an experiment parameter and can be changed in `stocks/config.py` before a new experiment begins.

### Data source

V1 uses the Yahoo Finance chart endpoint as a **zero-key prototype adapter**. It is intentionally isolated behind `stocks/provider_yahoo.py`.

It is **not** treated as an official/licensed Borsa İstanbul feed. Before using BIST results for serious intraday evaluation, replace the adapter with a licensed Borsa İstanbul data vendor. For US equities, the provider can later be replaced with Alpaca Market Data or another production feed without changing the portfolio/AI engine.

### Trading assumptions

- no short selling
- no leverage
- US fractional shares supported in the simulator
- BIST uses whole-share quantities
- 0.10% broker-neutral simulated friction per side
- Stop keeps at least 70% cash and max 12% per position
- Endeks keeps at least 35% cash and max 22% per position
- Boğa keeps at least 5% cash and max 40% per position
- SELLs execute before BUYs
- BUY requests are scaled to cash floor and position caps
- repeated runs on the same market bar are skipped

The 0.10% friction is an experimental assumption, **not a statement of Midas's current fee schedule**.

### Manual test

```bash
python3 -m unittest discover -s tests -v

# Fetch market data and inspect prompts without model calls:
python3 -m stocks.tick --market us --force --dry-run
python3 -m stocks.tick --market bist --force --dry-run

# Full paper ticks require NVIDIA_API_KEY:
python3 -m stocks.tick --market us --force
python3 -m stocks.tick --market bist --force
```

GitHub Actions workflows:

- `US Stocks Tick`
- `BIST Stocks Tick`

Manual workflow runs bypass the session-hours guard, but the duplicate-bar guard remains active.
