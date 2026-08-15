"""Claude Code (headless) çağrısı.

Döndürdüğü sözleşme:
    {"ok": bool, "decisions": [...], "thesis": str, "raw": str,
     "usage": {...}, "error": str|None}
"""

import json
import re
import subprocess

from config import CLAUDE_DISALLOWED_TOOLS, CLAUDE_TIMEOUT

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def extract_json(text: str) -> dict:
    """Modelin çıktısından JSON'u çıkar. Fence ve önsöz toleranslı."""
    text = (text or "").strip()
    if not text:
        raise ValueError("boş yanıt")
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


def call_claude_code(prompt: str, model: str, effort: str | None) -> dict:
    cmd = ["claude", "-p", prompt, "--model", model]
    # Effort desteklemeyen modeller için bayrağı hiç gönderme.
    if effort:
        cmd += ["--effort", effort]
    cmd += [
        "--output-format", "json",
        "--disallowedTools", *CLAUDE_DISALLOWED_TOOLS,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=CLAUDE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return _fail(f"timeout ({CLAUDE_TIMEOUT}s)")

    if proc.returncode != 0:
        return _fail(f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[:300]}")

    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _fail("claude JSON zarfı okunamadı", proc.stdout[:300])

    # Limit/throttle burada görünür — gap olarak kaydedilmesi kritik.
    if env.get("is_error") or env.get("subtype") != "success":
        return _fail(f"claude: {env.get('subtype')} / {env.get('api_error_status')}",
                     str(env.get("result", ""))[:300])

    raw = env.get("result", "")
    u = env.get("usage", {}) or {}
    usage = {
        "cost_usd": env.get("total_cost_usd"),
        "input": u.get("input_tokens"),
        "output": u.get("output_tokens"),
        "cache_create": u.get("cache_creation_input_tokens"),
        "cache_read": u.get("cache_read_input_tokens"),
        "duration_ms": env.get("duration_ms"),
        "served_model": list((env.get("modelUsage") or {}).keys()),
    }
    try:
        return _normalize(extract_json(raw), raw, usage)
    except (ValueError, json.JSONDecodeError) as e:
        return _fail(f"JSON parse: {e}", raw[:300])


def call(agent: dict, prompt: str) -> dict:
    return call_claude_code(prompt, agent["model"], agent.get("effort"))
