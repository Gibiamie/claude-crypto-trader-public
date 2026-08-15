# claude-crypto-trader

Üç yapay zeka karakterine 10.000 dolar **sanal** para verilir; her saat başı
piyasaya bakıp kendi başlarına kripto alım-satım kararı verirler. Üçü de aynı
modeli (Claude Opus) ve aynı veriyi kullanır — **tek fark risk karakterleri**
(korkak / dengeli / cesur).

Asıl soru "yapay zeka para kazandı mı" değil: **alıp tutmaktan (HODL) iyi miydi?**

- **Paper trading** — gerçek para, cüzdan, private key, KYC yok. Sadece Hyperliquid'in
  public `/info` endpoint'inden fiyat okunur.
- Ücret (%0,07 taker) ve slippage (%0,05) simüle edilir; sonuçlar gerçeğe yakın çıkar.
- Her tick journal'a yazılır — `journal/<karakter>.jsonl`. Sitedeki leaderboard bu
  dosyaları okur. Veritabanı yok.

## Nasıl çalışır?

```
tick.py (saatlik)
  ├─ hl.py       Hyperliquid public /info → canlı fiyat + kapalı mumlar
  ├─ prompt.py   piyasa + portföy → prompt (persona dışında herkese aynı)
  ├─ agents.py   claude -p --model opus --effort max  (tool'suz, JSON al/ver)
  ├─ broker.py   paper broker: ücret + slippage, spot, kaldıraçsız + HODL benchmark
  └─ journal/<karakter>.jsonl   ← tek kaynak-of-truth (append-only)

web/  Next.js — journal dosyalarını okuyup leaderboard + grafikleri gösterir
```

## Gereksinim

- **Python 3.11+** (sadece stdlib, ek paket yok)
- **[Claude Code](https://claude.com/claude-code)** kurulu ve giriş yapılmış
  (`claude` komutu PATH'te çalışır olmalı). Bot modeli bunun üzerinden çağırır,
  ayrı API key gerekmez.

## Hızlı başlangıç

```bash
git clone <repo-url> claude-crypto-trader
cd claude-crypto-trader

python3 tick.py --dry-run          # promptu bas, model çağırma (bedava, önce bunu dene)
python3 tick.py                    # tüm karakterler için bir tick çalıştır
python3 tick.py --only temkinli    # tek karakter
```

`tick.py` her çalıştığında bir "saat" ilerletir: fiyatı çeker, üç karaktere de
karar sordurur, portföyleri günceller ve `journal/`'a yazar. **Saatlik cron'a**
koyunca deney kendi kendine yürür (aşağıda).

Env değişkeni gerekmez — tek şart `claude`'un giriş yapmış olması.

## Site (opsiyonel)

Leaderboard + zaman grafiği + günlük sonuçlar. `journal/` dosyalarını doğrudan
okur (aynı makinede, veritabanı yok).

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

Journal başka bir yerdeyse: `JOURNAL_DIR=/mutlak/yol/journal npm run dev`
(varsayılan: repo kökündeki `../journal`).

## Cron (saatlik)

```cron
PATH=/usr/local/bin:/usr/bin:/bin
0 * * * * cd /yol/claude-crypto-trader && flock -n /tmp/cct.lock python3 -u tick.py >> tick.log 2>&1
```

- `flock -n` üst üste binmeyi engeller (tick timeout'ta birkaç dakika sürebilir).
- **`PATH` şart** — cron'un varsayılan PATH'inde `claude` binary'si olmayabilir;
  `which claude` çıktısındaki dizini ekle.
- `python3 -u`: cron log'u süreç bitmeden dolsun diye (tamponlamayı kapatır).

## Tasarım kararları

**Fill fiyatı `allMids`'ten alınır, mum close'undan değil.** Hyperliquid'in
döndürdüğü son mum daima açıktır; onun close'unu fill yaparsan geleceği görmüş
olursun ve tüm sonuçlar sahte çıkar. Modele de sadece **kapalı** mumlar gösterilir.

**Spot pair isimleri `@index` formatında.** `UBTC/USDC` → `@142`, `UETH/USDC` →
`@151`, `HYPE/USDC` → `@107`. Sadece `PURR/USDC` okunabilir isim taşır. Okunabilir
isimle mum sorgusu boş döner. `config.ASSETS` bunu tutar; doğrulamak için:
`curl -s -X POST https://api.hyperliquid.xyz/info -d '{"type":"spotMeta"}'`

**Ücret simülasyonu kapatılamaz.** Taker %0,07 + slippage %0,05. Kapatmak sadece
agresif stratejiyi sahte şekilde iyi gösterir. Prompt modele bunu açıkça söyler.

**Hata = gap, sessiz atlama değil.** Model limiti dolar, network düşer ya da bozuk
JSON dönerse: portföy **değişmez** ve journal'a `gap: true` satırı yazılır.
Grafikte delik görünür — gizlemek yerine göstermek hem dürüst hem içerik.

**Açığa satış ve kaldıraç yok.** Broker seviyesinde bloklu; model elinde olmayan
coini SELL dese emir reddedilir.

## Karakterleri değiştirmek

`config.py` içindeki `AGENTS` listesi. Tek değişken **persona** (risk karakteri);
model, effort ve gösterilen veri üçünde de aynı — leaderboard'ın "risk iştahı
sonucu ne değiştiriyor" sorusunu ölçmesi buna bağlı. `id` alanını değiştirme
(journal dosyasının anahtarı); `name` serbestçe değişebilir.

## ⚠️ Maliyet uyarısı

Her tick, her karakter için model çağrısı yapar (`opus --effort max`). Saatlik ×
3 karakter azımsanacak bir kullanım değil. Canlıya almadan önce kotanı/harcama
limitini kontrol et. Denemek için önce `--dry-run` ve `--only` ile tek karakter
çalıştır.

Bu bir deneydir, **yatırım tavsiyesi değildir.**
