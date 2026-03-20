from __future__ import annotations

import os

from openai import OpenAI

from .base import PulseLLMProvider


class OpenAIProvider(PulseLLMProvider):
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("OPENAI_PULSE_MODEL", "gpt-4o-mini")

    def generate(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 220) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
