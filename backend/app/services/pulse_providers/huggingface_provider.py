from __future__ import annotations

import os
from typing import Any

import httpx

from .base import PulseLLMProvider


class HuggingFaceProvider(PulseLLMProvider):
    def __init__(self) -> None:
        self.api_token = os.getenv("HUGGINGFACE_API_TOKEN", "").strip()
        self.model_url = os.getenv("HUGGINGFACE_MODEL_URL", "").strip()
        self.timeout = float(os.getenv("HUGGINGFACE_TIMEOUT_SECONDS", "45"))
        if not self.api_token:
            raise RuntimeError("Missing HUGGINGFACE_API_TOKEN")
        if not self.model_url:
            raise RuntimeError("Missing HUGGINGFACE_MODEL_URL")

    def _extract_text(self, data: Any) -> str:
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                text = first.get("generated_text") or first.get("summary_text") or ""
                return str(text).strip()
        if isinstance(data, dict):
            if isinstance(data.get("generated_text"), str):
                return data["generated_text"].strip()
            if isinstance(data.get("answer"), str):
                return data["answer"].strip()
            if isinstance(data.get("error"), str):
                raise RuntimeError(data["error"])
        return ""

    def generate(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 220) -> str:
        prompt = (
            "<|system|>\n"
            f"{system_prompt}\n\n"
            "<|user|>\n"
            f"{user_prompt}\n\n"
            "<|assistant|>\n"
        )
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False,
                "do_sample": temperature > 0,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.model_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        text = self._extract_text(data)
        return text or ""
