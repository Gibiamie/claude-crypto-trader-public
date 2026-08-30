"""NVIDIA NIM (OpenAI-uyumlu) API çağrısı — build.nvidia.com üzerinden ücretsiz.

Döndürdüğü sözleşme (tick.py'nin beklediği, orijinal agents.py ile aynı):
    {"ok": bool, "decisions": [...], "thesis": str, "raw": str,
     "usage": {...}, "error": str|None}
"""

import json
import os
import re
import urllib.error
import urllib.request

from config import MODEL_TIMEOUT, NVIDIA_BASE_URL

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def extract_json(text: str) -> dict:
    """Modelin çıktısından JSON'u çıkar. Fence, düşünme bloğu ve önsöz toleranslı."""
    text = (text or "").strip()
    if not text:
        raise ValueError("boş yanıt")
    text = _THINK.sub("", text).strip()  # olası "düşünme" bloğunu at
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


def _normalize(parsed: dict, raw: str, usage: dict) -> dict:
    decisions = parsed.get("decisions") or []
    if not isinstance(decisions, list):
        raise ValueError("decisions liste değil")
    return {
        "ok": True,
        "decisions": decisions,
        "thesis": str(parsed.get("thesis", ""))[:600],
        "raw": raw,
        "usage": usage,
        "error": None,
    }


def _fail(err: str, raw: str = "") -> dict:
    return {"ok": False, "decisions": [], "thesis": "", "raw": raw,
            "usage": {}, "error": err}


def call_nvidia(prompt: str, model: str) -> dict:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return _fail("NVIDIA_API_KEY tanımlı değil")

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 1024,
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
        "cost_usd": 0.0,  # NVIDIA ücretsiz katman — gerçek maliyet yok
        "input": u.get("prompt_tokens"),
        "output": u.get("completion_tokens"),
        "cache_create": None,
        "cache_read": None,
        "duration_ms": None,
        "served_model": [model],
    }
    try:
        return _normalize(extract_json(raw), raw, usage)
    except (ValueError, json.JSONDecodeError) as e:
        return _fail(f"JSON parse: {e}", raw[:300])


def call(agent: dict, prompt: str) -> dict:
    return call_nvidia(prompt, agent["model"])
