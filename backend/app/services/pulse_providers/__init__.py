from __future__ import annotations

import os

from .base import PulseLLMProvider
from .huggingface_provider import HuggingFaceProvider
from .openai_provider import OpenAIProvider


def _build_provider(provider_name: str) -> PulseLLMProvider:
    name = (provider_name or "").strip().lower()
    if name == "huggingface":
        return HuggingFaceProvider()
    if name == "openai":
        return OpenAIProvider()
    raise RuntimeError(f"Unsupported PULSE provider: {provider_name}")


def get_pulse_provider() -> PulseLLMProvider:
    provider_name = os.getenv("PULSE_MODEL_PROVIDER", "huggingface")
    return _build_provider(provider_name)


def get_fallback_pulse_provider() -> PulseLLMProvider:
    fallback_name = os.getenv("PULSE_FALLBACK_PROVIDER", "openai").strip().lower()
    primary_name = os.getenv("PULSE_MODEL_PROVIDER", "huggingface").strip().lower()

    if not fallback_name or fallback_name == primary_name:
        raise RuntimeError("No fallback provider configured")
    return _build_provider(fallback_name)
