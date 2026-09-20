"""AI kararlarını gerçek snapshot değerleriyle deterministik olarak açıklar."""

import math


PCT_SIGNALS = {
    "change_5_pct",
    "change_20_pct",
    "rel_20_pct",
    "volatility_20_pct",
}


def _format_value(signal: str, value) -> str:
    if value is None:
        raise ValueError(f"{signal}: snapshot değeri yok")
    if isinstance(value, bool):
        raise ValueError(f"{signal}: sayısal değil")
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{signal}: sayısal değil")
    if not math.isfinite(v):
        raise ValueError(f"{signal}: finite değil")

    if signal in PCT_SIGNALS:
        return f"{signal}={v:.2f}%"
    if signal == "rsi14":
        return f"rsi14={v:.2f}"
    if signal in {"last", "sma20"}:
        return f"{signal}={v:.4f}"
    if signal == "volume_ratio":
        return f"volume_ratio={v:.2f}x"
    if signal == "score":
        return f"score={v:.3f}"
    return f"{signal}={v}"


def ground_orders(orders: list[dict], snapshot: dict, currency: str) -> tuple[list[dict], str]:
    by_symbol = {row["symbol"]: row for row in snapshot.get("all_symbols", [])}
    grounded = []
    thesis_parts = []

    for order in orders:
        symbol = order["symbol"]
        metrics = by_symbol.get(symbol)
        if metrics is None:
            raise ValueError(f"{symbol}: snapshot satırı bulunamadı")

        signal_text = []
        for signal in order["signals"]:
            signal_text.append(_format_value(signal, metrics.get(signal)))

        out = dict(order)
        out["reason"] = "; ".join(signal_text)
        grounded.append(out)

        thesis_parts.append(
            f"{order['action']} {symbol} {order['notional']:.2f} {currency} "
            f"(confidence={order['confidence']:.2f}) · " + ", ".join(signal_text)
        )

    thesis = " | ".join(thesis_parts) if thesis_parts else "Bu tick için işlem yok."
    return grounded, thesis
