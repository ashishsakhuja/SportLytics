from __future__ import annotations

import os

from .base import PulseLLMProvider
from .huggingface_provider import HuggingFaceProvider
from .openai_provider import OpenAIProvider


def get_pulse_provider() -> PulseLLMProvider:
    provider_name = os.getenv("PULSE_MODEL_PROVIDER", "huggingface").strip().lower()
    if provider_name == "huggingface":
        return HuggingFaceProvider()
    if provider_name == "openai":
        return OpenAIProvider()
    raise RuntimeError(f"Unsupported PULSE_MODEL_PROVIDER: {provider_name}")
