"""Deney konfigürasyonu — tüm parametreler tek dosyada."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
JOURNAL_DIR = ROOT / "journal"

# Hyperliquid spot pair `name` değerleri. Spot'ta pair adı @index formatında —
# sadece PURR/USDC okunabilir isim taşır. spotMeta'dan doğrulanabilir:
#   curl -s -X POST https://api.hyperliquid.xyz/info -d '{"type":"spotMeta"}'
ASSETS = {
    "BTC": "@142",   # UBTC/USDC
    "ETH": "@151",   # UETH/USDC
    "HYPE": "@107",  # HYPE/USDC
}

START_CASH = 10_000.0

INTERVAL = "1h"
CANDLE_LOOKBACK = 72      # modele gösterilecek KAPALI mum sayısı (3 gün)

TAKER_FEE = 0.0007        # %0.07 — Hyperliquid spot taker
SLIPPAGE = 0.0005         # %0.05 — ince order book payı
MIN_TRADE_USD = 25.0      # altındaki emirler ücret gürültüsü, reddedilir

# NVIDIA NIM (build.nvidia.com) — OpenAI-uyumlu, ücretsiz katman.
# Kart istemiyor, dakikada ~40 istek sınırı var (biz saatte 3 istek yapıyoruz).
# Model değiştirmek istersen: https://build.nvidia.com katalogundan başka bir
# `org/model-adı` seç ve burada değiştir — tek yer, her şeyi etkiler.
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
MODEL_TIMEOUT = 180

# Üç agent da AYNI model + AYNI veriyi alır. Tek değişken risk profili.
# Leaderboard bu yüzden model kıyası değil strateji kıyasıdır: "risk iştahı sonucu
# ne kadar değiştiriyor?"
#
# `id`   → kalıcı anahtar (journal dosyası). DEĞİŞTİRME, veriyi bozar.
# `name` → sitede gösterilen isim. Serbestçe değiştirilebilir.
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
