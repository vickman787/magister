from __future__ import annotations

import json
import os

from openai import OpenAI


class LLM:
    def __init__(self, cfg: dict) -> None:
        self.model = os.getenv("LLM_MODEL") or cfg.get("model", "gpt-4o-mini")
        self.base_url = os.getenv("LLM_BASE_URL") or cfg.get("base_url", "https://api.openai.com/v1")
        self.temperature = float(cfg.get("temperature", 0.2))
        api_key_env = cfg.get("api_key_env", "OPENAI_API_KEY")
        self.client = OpenAI(api_key=os.getenv(api_key_env), base_url=self.base_url)

    def chat(self, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    def propose(self, prompt_user: str) -> list[dict]:
        system = (
            "You are a conservative crypto portfolio analyst. "
            "Return ONLY valid JSON matching the requested schema. No markdown, no commentary."
        )
        raw = self.chat(system, prompt_user)
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> list[dict]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
        data = json.loads(cleaned)
        if isinstance(data, dict):
            data = data.get("proposals", [])
        return data
