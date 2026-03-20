from __future__ import annotations

import os

from openai import OpenAI

from .base import PulseLLMProvider


class HuggingFaceProvider(PulseLLMProvider):
    def __init__(self) -> None:
        self.api_token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
        if not self.api_token:
            raise RuntimeError("Missing HUGGINGFACE_API_TOKEN")

        self.base_url = os.getenv("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1").strip()
        self.model = os.getenv(
            "HUGGINGFACE_MODEL",
            "mistralai/Mistral-7B-Instruct-v0.2:featherless-ai",
        ).strip()
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_token)

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.35,
        max_tokens: int = 400,
    ) -> str:
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
