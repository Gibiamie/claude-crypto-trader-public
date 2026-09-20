import "./globals.css";

export const metadata = {
  title: "AI Market Trader Lab",
  description:
    "Crypto, US stocks ve BIST için bağımsız paper-trading deneyleri; AI kararları, portföyler ve benchmark karşılaştırmaları.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="tr">
      <body>
        <header className="site-header">
          <a href="/" className="brand">
            ai<span>·</span>market<span>·</span>lab
          </a>
          <nav className="market-nav" aria-label="Piyasalar">
            <a href="/">Crypto</a>
            <a href="/stocks/us">US Stocks</a>
            <a href="/stocks/bist">BIST</a>
          </nav>
          <p className="tagline">
            Aynı risk karakterleri, farklı piyasalarda bağımsız paper portföyler yönetiyor.
          </p>
          <p className="disclaimer">
            <strong>Yatırım tavsiyesi değildir.</strong> Sistem paper simulation&apos;dır ve
            Midas hesabına otomatik emir göndermez. Her piyasanın veri kaynağı ve benchmarkı
            kendi sayfasında açıkça belirtilir.
          </p>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
