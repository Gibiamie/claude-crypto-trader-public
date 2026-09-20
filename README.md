# claude-crypto-trader — V2

Three AI risk personas paper-trade BTC, ETH and HYPE with the same market data and the same model settings.

The experiment asks one narrow question:

> How much does risk persona change portfolio behaviour and performance when model and inputs are held constant?

No real money, wallet, private key or KYC is used.

## Active experiment

`v2-2026-09-20`

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
  └─ state/v2-2026-09-20/*.json  ← persisted back to GitHub

Vercel / Next.js
  └─ reads active experiment rows and renders the dashboard
```

## Why V2 exists

The original GitHub Actions workflow persisted only `journal/*.jsonl`, while the paper broker stored portfolio and HODL state under ignored `state/`.

Because GitHub-hosted runners are ephemeral, every run effectively started from a fresh $10,000 portfolio and recreated the HODL benchmark.

V2 fixes this by persisting both journal and state, while also storing a full `portfolio_state` snapshot in every V2 journal row as a recovery path.

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
