from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..config import get_settings

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), autoescape=select_autoescape())


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
                content = resp.json()["choices"][0]["message"]["content"]
                return json.loads(content)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                if attempt == 2:
                    raise
                continue
        raise RuntimeError("unreachable")
