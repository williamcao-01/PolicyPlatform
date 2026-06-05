from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class DeepSeekSettings:
    api_key: str | None
    base_url: str
    model: str
    use_real_llm: bool


def load_deepseek_settings() -> DeepSeekSettings:
    return DeepSeekSettings(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        use_real_llm=os.getenv("USE_REAL_LLM", "false").lower() == "true",
    )


def assert_llm_ready() -> None:
    settings = load_deepseek_settings()
    if settings.use_real_llm and not settings.api_key:
        raise RuntimeError("USE_REAL_LLM=true requires DEEPSEEK_API_KEY.")


class DeepSeekClient:
    def __init__(self, settings: DeepSeekSettings | None = None) -> None:
        self.settings = settings or load_deepseek_settings()

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.settings.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for real LLM skill execution.")
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=90) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        import json

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            repair_payload = {
                "model": self.settings.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是JSON修复器。只输出合法JSON对象，不要解释，不要markdown。",
                    },
                    {
                        "role": "user",
                        "content": (
                            "把下面内容修复为合法JSON对象，保持字段含义不变。"
                            "如果缺失必要标点，补齐标点。内容：\n"
                            f"{content}"
                        ),
                    },
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
            with httpx.Client(timeout=90) as client:
                repair_response = client.post(url, json=repair_payload, headers=headers)
                repair_response.raise_for_status()
                repair_data = repair_response.json()
            repaired = repair_data["choices"][0]["message"]["content"]
            return json.loads(repaired)
