import "./globals.css";

export const metadata = {
  title: "Claude Crypto Trader",
  description:
    "Claude Opus 5 saatlik olarak spot kripto kararı veriyor. Kararlar, gerekçeler ve kâr/zarar canlı yayında.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="tr">
      <body>
        <header className="site-header">
          <a href="/" className="brand">
            claude<span>·</span>crypto<span>·</span>trader
          </a>
          <p className="tagline">
            Üç yapay zeka karakteri, her saat başı kripto alıp satıyor. Sanal parayla.
          </p>
          <p className="disclaimer">
            <strong>Yatırım tavsiyesi değildir.</strong> Bu bir deney. Gerçek para
            yok, hepsi sanal. Fiyatlar Hyperliquid borsasından canlı alınıyor. Her
            işlemden %0,07 komisyon ve %0,05 fiyat kayması düşülüyor, yani sonuçlar
            gerçeğe yakın çıkıyor.
          </p>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
