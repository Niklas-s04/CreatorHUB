from __future__ import annotations

import json
import time
from typing import Any, Optional

import requests

from app.core.config import settings


class OllamaError(RuntimeError):
    pass


def ollama_chat(model: str, system: str, user: str, images_b64: Optional[list[str]] = None, force_json: bool = True) -> tuple[str, dict]:
    """Call Ollama chat API and return (content, meta)."""
    url = f"{settings.OLLAMA_URL.rstrip('/')}/api/chat"
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    user_msg: dict[str, Any] = {"role": "user", "content": user}
    if images_b64:
        user_msg["images"] = images_b64
    messages.append(user_msg)

    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    if force_json:
        payload["format"] = "json"

    t0 = time.time()
    r = requests.post(url, json=payload, timeout=180)
    dt = time.time() - t0

    if r.status_code != 200:
        raise OllamaError(f"Ollama error {r.status_code}: {r.text[:500]}")
    data = r.json()
    content = (data.get("message") or {}).get("content") or ""
    meta = {k: v for k, v in data.items() if k != "message"}
    meta["duration_sec"] = round(dt, 3)
    return content, meta


def ensure_json(text: str) -> Any:
    """Parse JSON output; tolerates surrounding text."""
    text = text.strip()
    # Direkter JSON-Parse.
    try:
        return json.loads(text)
    except Exception:
        pass
    # Erstes JSON-Objekt oder -Array aus Freitext extrahieren.
    start = min([i for i in [text.find('{'), text.find('[')] if i != -1], default=-1)
    if start == -1:
        raise ValueError("No JSON start found")
    # Einfache Klammerlogik zum Finden des JSON-Endes.
    stack = []
    end = None
    for i in range(start, len(text)):
        ch = text[i]
        if ch in '{[':
            stack.append(ch)
        elif ch in '}]':
            if not stack:
                continue
            op = stack.pop()
            if not stack:
                end = i + 1
                break
    if end is None:
        raise ValueError("No JSON end found")
    return json.loads(text[start:end])


def safe_ollama_json(model: str, system: str, user: str, images_b64: Optional[list[str]] = None, max_fix_attempts: int = 1) -> tuple[dict, dict]:
    """Call Ollama, parse JSON; if parsing fails, do one repair pass."""
    content, meta = ollama_chat(model=model, system=system, user=user, images_b64=images_b64, force_json=True)
    try:
        return ensure_json(content), meta
    except Exception as e:
        if max_fix_attempts <= 0:
            raise
        fix_system = "You are a JSON repair utility. Output ONLY valid JSON."
        fix_user = f"Fix to valid JSON only. Original:\n{content}"
        fixed, meta2 = ollama_chat(model=model, system=fix_system, user=fix_user, images_b64=None, force_json=True)
        return ensure_json(fixed), {**meta, "repair": meta2}
