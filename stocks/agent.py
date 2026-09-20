"""Hisse deneyleri için dinamik sembol setli NVIDIA NIM istemcisi."""

import json
import math
import os
import re
import urllib.error
import urllib.request

from .config import (
    ALLOWED_SIGNALS,
    MODEL_MAX_TOKENS,
    MODEL_REPAIR_ATTEMPTS,
    MODEL_TEMPERATURE,
    MODEL_TIMEOUT,
    NVIDIA_BASE_URL,
    NVIDIA_MODEL,
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def extract_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("boş yanıt")
    text = _THINK.sub("", text).strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start < 0:
        raise ValueError("JSON bulunamadı")
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("JSON kapanmadı")


def validate_payload(
    parsed: dict,
    allowed_symbols: set[str],
    held_symbols: set[str],
    max_orders: int,
    require_buy: bool,
) -> dict:
    if not isinstance(parsed, dict):
        raise ValueError("üst seviye JSON object değil")

    orders = parsed.get("orders")
    if not isinstance(orders, list):
        raise ValueError("orders liste değil")
    if len(orders) > max_orders:
        raise ValueError(f"en fazla {max_orders} emir verilebilir")

    normalized = []
    seen = set()
    buys = 0

    for order in orders:
        if not isinstance(order, dict):
            raise ValueError("emir object değil")

        symbol = str(order.get("symbol", "")).upper().strip()
        action = str(order.get("action", "")).upper().strip()
        if symbol not in allowed_symbols:
            raise ValueError(f"izin verilmeyen sembol: {symbol}")
        if symbol in seen:
            raise ValueError(f"tekrarlanan sembol: {symbol}")
        if action not in {"BUY", "SELL"}:
            raise ValueError(f"geçersiz action: {action}")
        if action == "SELL" and symbol not in held_symbols:
            raise ValueError(f"{symbol}: elde olmayan hisse satılamaz")

        try:
            notional = float(order.get("notional") or 0)
            confidence = float(order.get("confidence"))
        except (TypeError, ValueError):
            raise ValueError(f"{symbol}: notional/confidence sayı değil")

        if not math.isfinite(notional) or notional <= 0:
            raise ValueError(f"{symbol}: notional > 0 olmalı")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"{symbol}: confidence 0-1 dışında")

        signals = order.get("signals") or []
        if not isinstance(signals, list):
            raise ValueError(f"{symbol}: signals liste değil")
        signals = [str(x) for x in signals]
        if any(sig not in ALLOWED_SIGNALS for sig in signals):
            raise ValueError(f"{symbol}: bilinmeyen signal")
        if not signals:
            raise ValueError(f"{symbol}: en az bir signal gerekli")

        reason = str(order.get("reason", "")).strip()
        if not reason:
            raise ValueError(f"{symbol}: reason boş")

        seen.add(symbol)
        buys += int(action == "BUY")
        normalized.append({
            "symbol": symbol,
            "action": action,
            "notional": round(notional, 6),
            "confidence": confidence,
            "signals": signals,
            "reason": reason[:300],
        })

    if require_buy and buys == 0:
        raise ValueError("ilk giriş turunda en az bir BUY gerekli")

    thesis = str(parsed.get("thesis", "")).strip()
    if not thesis:
        raise ValueError("thesis boş")

    return {"orders": normalized, "thesis": thesis[:700]}


def _fail(error: str, raw: str = "", usage: dict | None = None) -> dict:
    return {
        "ok": False,
        "orders": [],
        "thesis": "",
        "raw": raw,
        "usage": usage or {},
        "error": error,
        "repaired": False,
    }


def _one_call(prompt: str) -> tuple[str, dict] | dict:
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        return _fail("NVIDIA_API_KEY tanımlı değil")

    body = json.dumps({
        "model": NVIDIA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": MODEL_TEMPERATURE,
        "max_tokens": MODEL_MAX_TOKENS,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{NVIDIA_BASE_URL}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=MODEL_TIMEOUT) as resp:
            env = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        return _fail(f"HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        return _fail(f"network: {e.reason}")
    except TimeoutError:
        return _fail(f"timeout ({MODEL_TIMEOUT}s)")

    choices = env.get("choices") or []
    if not choices:
        return _fail("boş choices")

    raw = choices[0].get("message", {}).get("content", "")
    u = env.get("usage") or {}
    return raw, {
        "cost_usd": 0.0,
        "input": u.get("prompt_tokens"),
        "output": u.get("completion_tokens"),
        "served_model": [NVIDIA_MODEL],
    }


def call(
    prompt: str,
    allowed_symbols: set[str],
    held_symbols: set[str],
    max_orders: int,
    require_buy: bool,
) -> dict:
    attempt_prompt = prompt
    total_usage = {"input": 0, "output": 0, "cost_usd": 0.0, "served_model": []}
    last_raw = ""
    last_error = ""

    for attempt in range(MODEL_REPAIR_ATTEMPTS + 1):
        result = _one_call(attempt_prompt)
        if isinstance(result, dict):
            return result
        raw, usage = result
        last_raw = raw
        total_usage["input"] += usage.get("input") or 0
        total_usage["output"] += usage.get("output") or 0
        total_usage["served_model"] = list(dict.fromkeys(
            total_usage["served_model"] + (usage.get("served_model") or [])
        ))

        try:
            parsed = validate_payload(
                extract_json(raw),
                allowed_symbols=allowed_symbols,
                held_symbols=held_symbols,
                max_orders=max_orders,
                require_buy=require_buy,
            )
            return {
                "ok": True,
                "orders": parsed["orders"],
                "thesis": parsed["thesis"],
                "raw": raw,
                "usage": total_usage,
                "error": None,
                "repaired": attempt > 0,
            }
        except (ValueError, json.JSONDecodeError) as e:
            last_error = str(e)
            if attempt >= MODEL_REPAIR_ATTEMPTS:
                break
            first = " En az bir BUY zorunlu." if require_buy else ""
            held = ", ".join(sorted(held_symbols)) or "YOK"
            allowed = ", ".join(sorted(allowed_symbols))
            attempt_prompt = (
                "Önceki cevap geçersiz. YALNIZ JSON döndür. "
                f"İzinli semboller: {allowed}. Elde olanlar: {held}. "
                f"En fazla {max_orders} emir. action yalnız BUY/SELL. "
                "Elde olmayan hisse için SELL verme. notional > 0, confidence 0-1. "
                "signals yalnız izinli teknik alan adlarından oluşsun; reason ve thesis boş olmasın."
                f"{first}\n\nGEÇERSİZ CEVAP:\n{raw[:5000]}"
            )

    return _fail(f"JSON/schema: {last_error}", last_raw[:1200], total_usage)
