"""US/BIST paper deney konfigürasyonu."""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNAL_ROOT = ROOT / "stock_journal"
STATE_ROOT = ROOT / "stock_state"

STOCK_SCHEMA_VERSION = 2
STOCK_STRATEGY_VERSION = "v1.1.0"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
MODEL_TIMEOUT = 180
MODEL_TEMPERATURE = 0.0
MODEL_MAX_TOKENS = 900
MODEL_REPAIR_ATTEMPTS = 1

DATA_SOURCE = "Yahoo Finance chart endpoint (prototype, unofficial)"
INTERVAL = "60m"
RANGE = "10d"
CANDIDATE_COUNT = 8
MIN_VALID_SYMBOLS = 5


@dataclass(frozen=True)
class MarketConfig:
    id: str
    name: str
    currency: str
    start_cash: float
    benchmark_symbol: str
    benchmark_name: str
    experiment_id: str
    timezone: str
    open_hour: int
    open_minute: int
    close_hour: int
    close_minute: int
    unit_step: float
    friction_rate: float
    universe: tuple[str, ...]


MARKETS = {
    "us": MarketConfig(
        id="us",
        name="US Stocks",
        currency="USD",
        start_cash=10_000.0,
        benchmark_symbol="SPY",
        benchmark_name="SPY",
        experiment_id="us-v1.1-2026-09-21",
        timezone="America/New_York",
        open_hour=9,
        open_minute=30,
        close_hour=16,
        close_minute=0,
        unit_step=0.0001,
        # Broker-specific commission değildir; paper sim için birleşik sürtünme varsayımı.
        friction_rate=0.0010,
        universe=(
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
            "AMD", "MU", "NFLX", "PLTR", "JPM", "BAC", "GS", "XOM", "CVX",
            "LLY", "UNH", "COST", "WMT", "PWR", "FCX", "ASML",
        ),
    ),
    "bist": MarketConfig(
        id="bist",
        name="BIST",
        currency="TRY",
        start_cash=100_000.0,
        benchmark_symbol="XU100.IS",
        benchmark_name="BIST 100",
        experiment_id="bist-v1.1-2026-09-21",
        timezone="Europe/Istanbul",
        open_hour=10,
        open_minute=0,
        close_hour=18,
        close_minute=0,
        unit_step=1.0,
        friction_rate=0.0010,
        universe=(
            "THYAO.IS", "TUPRS.IS", "ASELS.IS", "BIMAS.IS", "KCHOL.IS", "SAHOL.IS",
            "ISCTR.IS", "AKBNK.IS", "YKBNK.IS", "GARAN.IS", "FROTO.IS", "TOASO.IS",
            "EREGL.IS", "KRDMD.IS", "SISE.IS", "SASA.IS", "HEKTS.IS", "ENKAI.IS",
            "TCELL.IS", "TTKOM.IS", "PETKM.IS", "ALARK.IS", "MGROS.IS", "ULKER.IS",
        ),
    ),
}


AGENTS = [
    {
        "id": "temkinli",
        "name": "Stop",
        "min_cash_pct": 0.70,
        "max_position_pct": 0.12,
        "max_orders": 3,
        "persona": (
            "Temkinli yatırımcısın. Sermaye koruması önceliklidir. "
            "Yalnız verilen veride güçlü gerekçe varsa küçük pozisyon açarsın."
        ),
    },
    {
        "id": "dengeli",
        "name": "Endeks",
        "min_cash_pct": 0.35,
        "max_position_pct": 0.22,
        "max_orders": 5,
        "persona": (
            "Dengeli yatırımcısın. Nakit ve riskli varlıklar arasında denge kurarsın; "
            "tek hisseye aşırı yoğunlaşmazsın."
        ),
    },
    {
        "id": "risksever",
        "name": "Boğa",
        "min_cash_pct": 0.05,
        "max_position_pct": 0.40,
        "max_orders": 5,
        "persona": (
            "Agresif yatırımcısın. Güçlü momentum ve göreli güç gördüğünde daha yüksek "
            "sermaye kullanırsın; yine de yalnız verilen veriye dayanırsın."
        ),
    },
]


ALLOWED_SIGNALS = {
    "last",
    "sma20",
    "rsi14",
    "change_5_pct",
    "change_20_pct",
    "rel_20_pct",
    "volume_ratio",
    "volatility_20_pct",
    "score",
}
