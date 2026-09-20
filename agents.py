"""NVIDIA NIM çağrısı + sıkı JSON doğrulaması ve tek repair retry."""

import json
import math
import os
import re
import urllib.error
import urllib.request

from config import (
    ASSETS,
    MODEL_MAX_TOKENS,
    MODEL_REPAIR_ATTEMPTS,
    MODEL_TEMPERATURE,
    MODEL_TIMEOUT,
    NVIDIA_BASE_URL,
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
VALID_ACTIONS = {"BUY", "SELL", "HOLD"}


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
    if start == -1:
        raise ValueError(f"JSON bulunamadı: {text[:200]}")
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
    raise ValueError(f"JSON kapanmadı: {text[:200]}")


def validate_payload(parsed: dict) -> dict:
    if not isinstance(parsed, dict):
        raise ValueError("üst seviye JSON object değil")
    decisions = parsed.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("decisions liste değil")
    if len(decisions) != len(ASSETS):
        raise ValueError(f"tam {len(ASSETS)} karar gerekli")

    normalized = []
    seen = set()
    for d in decisions:
        if not isinstance(d, dict):
            raise ValueError("karar object değil")
        coin = str(d.get("coin", "")).upper().strip()
        action = str(d.get("action", "")).upper().strip()
        if coin not in ASSETS:
            raise ValueError(f"bilinmeyen coin: {coin}")
        if coin in seen:
            raise ValueError(f"tekrarlanan coin: {coin}")
        if action not in VALID_ACTIONS:
            raise ValueError(f"geçersiz action: {action}")
        seen.add(coin)

        try:
            usd = float(d.get("usd") or 0)
            confidence = float(d.get("confidence"))
        except (TypeError, ValueError):
            raise ValueError(f"{coin}: usd/confidence sayı değil")
        if not math.isfinite(usd) or usd < 0:
            raise ValueError(f"{coin}: usd geçersiz")
        if action in ("BUY", "SELL") and usd <= 0:
            raise ValueError(f"{coin}: {action} için usd > 0 olmalı")
        if action == "HOLD":
            usd = 0.0
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"{coin}: confidence 0-1 dışında")

        normalized.append({
            "coin": coin,
            "action": action,
            "usd": round(usd, 6),
            "confidence": confidence,
            "reason": str(d.get("reason", ""))[:300],
        })

    if seen != set(ASSETS):
        raise ValueError("her varlık için tam bir karar gerekli")

    return {
        "decisions": normalized,
        "thesis": str(parsed.get("thesis", ""))[:600],
    }


def _fail(err: str, raw: str = "", usage: dict | None = None) -> dict:
    return {
        "ok": False,
        "decisions": [],
        "thesis": "",
        "raw": raw,
        "usage": usage or {},
        "error": err,
    }


def _merge_usage(total: dict, add: dict) -> dict:
    out = dict(total)
    for k in ("input", "output"):
        out[k] = (out.get(k) or 0) + (add.get(k) or 0)
    out["cost_usd"] = (out.get("cost_usd") or 0) + (add.get("cost_usd") or 0)
    out["cache_create"] = None
    out["cache_read"] = None
    out["duration_ms"] = None
    models = list(dict.fromkeys((out.get("served_model") or []) + (add.get("served_model") or [])))
    out["served_model"] = models
    return out


def _one_call(prompt: str, model: str) -> tuple[str, dict] | dict:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return _fail("NVIDIA_API_KEY tanımlı değil")

    body = json.dumps({
        "model": model,
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
            "Authorization": f"Bearer {api_key}",
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
        return _fail("boş choices", json.dumps(env)[:300])

    raw = choices[0].get("message", {}).get("content", "")
    u = env.get("usage", {}) or {}
    usage = {
        "cost_usd": 0.0,
        "input": u.get("prompt_tokens"),
        "output": u.get("completion_tokens"),
        "cache_create": None,
        "cache_read": None,
        "duration_ms": None,
        "served_model": [model],
    }
    return raw, usage


def call_nvidia(prompt: str, model: str) -> dict:
    attempt_prompt = prompt
    total_usage = {}
    last_raw = ""
    last_error = ""

    for attempt in range(MODEL_REPAIR_ATTEMPTS + 1):
        result = _one_call(attempt_prompt, model)
        if isinstance(result, dict):
            return result

        raw, usage = result
        last_raw = raw
        total_usage = _merge_usage(total_usage, usage)

        try:
            parsed = validate_payload(extract_json(raw))
            return {
                "ok": True,
                "decisions": parsed["decisions"],
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
            attempt_prompt = (
                "Aşağıdaki yanıt geçersiz. Yalnızca geçerli JSON döndür. "
                "BTC, ETH ve HYPE için tam birer karar olmalı; coin tekrarı olmasın. "
                "action yalnız BUY, SELL veya HOLD; confidence 0 ile 1 arasında. "
                "BUY/SELL için usd > 0, HOLD için usd 0 olsun. Açıklama/markdown yazma.\n\n"
                f"GEÇERSİZ YANIT:\n{raw[:5000]}"
            )

    return _fail(f"JSON/schema parse: {last_error}", last_raw[:1000], total_usage)


def call(agent: dict, prompt: str) -> dict:
    return call_nvidia(prompt, agent["model"])
