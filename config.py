"""Deney konfigürasyonu — tüm parametreler tek dosyada."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JOURNAL_DIR = ROOT / "journal"

# V1/Phase 0 satırları journal dosyalarında korunur ancak aktif deneyden ayrılır.
# Yeni bir metodoloji/model değişikliğinde yeni bir EXPERIMENT_ID kullan.
EXPERIMENT_ID = os.environ.get("EXPERIMENT_ID", "v2-2026-09-20")
SCHEMA_VERSION = 2
STRATEGY_VERSION = "v2.0.0"

# GitHub Actions runner geçicidir; bu klasör workflow sonunda repoya commit edilir.
STATE_DIR = ROOT / "state" / EXPERIMENT_ID

# Hyperliquid spot pair `name` değerleri.
ASSETS = {
    "BTC": "@142",   # UBTC/USDC
    "ETH": "@151",   # UETH/USDC
    "HYPE": "@107",  # HYPE/USDC
}

START_CASH = 10_000.0

INTERVAL = "1h"
CANDLE_LOOKBACK = 72

TAKER_FEE = 0.0007
SLIPPAGE = 0.0005
MIN_TRADE_USD = 25.0

# NVIDIA NIM — OpenAI uyumlu.
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
MODEL_TIMEOUT = 180
MODEL_TEMPERATURE = 0.0
MODEL_MAX_TOKENS = 1024
MODEL_REPAIR_ATTEMPTS = 1

# Üç agent aynı model + aynı veri + aynı inference ayarlarını alır.
# Kontrollü değişken yalnız risk personasıdır.
AGENTS = [
    {
        "id": "temkinli", "name": "Stop", "label": "Stop",
        "tagline": "Az yatırır, çok bekler. Para kaybetmekten korkar.",
        "model": NVIDIA_MODEL, "effort": None,
        "persona": (
            "SENİN ADIN STOP. Temkinli bir yatırımcısın.\n"
            "- Paranın çoğunu nakitte tutarsın. Az yatırım yaparsın.\n"
            "- Sadece çok emin olduğunda alırsın. Şüphen varsa almazsın.\n"
            "- Aynı anda çok az sayıda varlık tutarsın.\n"
            "- Zarar etmeye başlarsan hemen çıkarsın.\n"
            "- Fırsat kaçırmak seni üzmez. Para kaybetmek seni daha çok üzer."
        ),
    },
    {
        "id": "dengeli", "name": "Endeks", "label": "Endeks",
        "tagline": "Yarısını yatırır, yarısını bekletir. Ortada durur.",
        "model": NVIDIA_MODEL, "effort": None,
        "persona": (
            "SENİN ADIN ENDEKS. Dengeli bir yatırımcısın.\n"
            "- Paranın bir kısmını yatırır, bir kısmını nakitte tutarsın.\n"
            "- Ne çok cesur ne çok korkak davranırsın.\n"
            "- Yeterli neden varsa alırsın. Yoksa beklersin.\n"
            "- Paranı tek bir varlığa yatırmazsın. Çok fazla varlığa da dağıtmazsın.\n"
            "- Kazanma ve kaybetme ihtimalini birlikte düşünürsün."
        ),
    },
    {
        "id": "risksever", "name": "Boğa", "label": "Boğa",
        "tagline": "Neredeyse hepsini yatırır. Beklemeyi kayıp sayar.",
        "model": NVIDIA_MODEL, "effort": None,
        "persona": (
            "SENİN ADIN BOĞA. Cesur bir yatırımcısın.\n"
            "- Paranın neredeyse tamamını yatırırsın. Nakit sana kayıp gibi gelir.\n"
            "- Beğendiğin varlığa çok para koyarsın.\n"
            "- Ek kanıt beklemezsin. Fiyat yükselmeye başlayınca hemen alırsın.\n"
            "- Fiyat düşerse bunu normal karşılarsın.\n"
            "- Yine de bir nedenin olmadan alım yapmazsın."
        ),
    },
]
