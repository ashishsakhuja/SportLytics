from __future__ import annotations

from abc import ABC, abstractmethod


class PulseLLMProvider(ABC):
    @abstractmethod
    def generate(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 220) -> str:
        raise NotImplementedError
