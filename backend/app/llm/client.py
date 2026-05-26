from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any
import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..config import get_settings

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), autoescape=select_autoescape())

log = logging.getLogger("app.llm")

# (input USD per 1M tokens, output USD per 1M tokens). 모르면 0 — 비용 0으로 표시.
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o":         (2.50, 10.00),
    "gpt-4o-mini":    (0.15,  0.60),
    "gpt-4.1":        (2.00,  8.00),
    "gpt-4.1-mini":   (0.40,  1.60),
    "gpt-4.1-nano":   (0.10,  0.40),
    "o3-mini":        (1.10,  4.40),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022":  (0.80,  4.00),
    "claude-sonnet-4-5":          (3.00, 15.00),
    "claude-haiku-4-5":           (1.00,  5.00),
}

# 세션 누적 (프로세스 살아있는 동안)
_TOTAL = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "usd": 0.0}


def _estimate_usd(model: str, prompt_t: int, completion_t: int) -> float:
    p_in, p_out = _PRICING.get(model, (0.0, 0.0))
    return prompt_t / 1_000_000 * p_in + completion_t / 1_000_000 * p_out


def session_totals() -> dict[str, float]:
    return dict(_TOTAL)


def render(template: str, **vars: Any) -> str:
    return _env.get_template(f"{template}.j2").render(**vars)


def _load_fixture(name: str) -> dict[str, Any]:
    s = get_settings()
    assert s.llm_fixture_dir, "LLM_FIXTURE_DIR not set"
    path = Path(s.llm_fixture_dir) / f"{name}.json"
    return json.loads(path.read_text())


async def complete_json(template: str, fixture_name: str, **vars: Any) -> dict[str, Any]:
    """프롬프트를 렌더하고 OpenAI 호환 API에 호출. JSON 응답을 강제.

    `LLM_FIXTURE_DIR` 환경변수가 설정되면 실제 호출 없이 fixture_name 파일을 읽어 반환.
    """
    s = get_settings()
    if s.llm_fixture_dir:
        return _load_fixture(fixture_name)

    prompt = render(template, **vars)
    payload = {
        "model": s.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
    }
    headers = {"Authorization": f"Bearer {s.llm_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as cli:
        for attempt in range(3):
            try:
                resp = await cli.post(f"{s.llm_base_url}/chat/completions",
                                      json=payload, headers=headers)
                resp.raise_for_status()
                body = resp.json()
                content = body["choices"][0]["message"]["content"]
                usage = body.get("usage") or {}
                p_t = int(usage.get("prompt_tokens", 0))
                c_t = int(usage.get("completion_tokens", 0))
                usd = _estimate_usd(s.llm_model, p_t, c_t)
                _TOTAL["calls"] += 1
                _TOTAL["prompt_tokens"] += p_t
                _TOTAL["completion_tokens"] += c_t
                _TOTAL["usd"] += usd
                log.info("llm template=%s model=%s prompt=%d completion=%d est=$%.5f total_calls=%d total_usd=$%.4f",
                         template, s.llm_model, p_t, c_t, usd,
                         _TOTAL["calls"], _TOTAL["usd"])
                return json.loads(content)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                if attempt == 2:
                    raise
                continue
        raise RuntimeError("unreachable")
