"""Common interface every LLM provider adapter implements."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(RuntimeError):
    """Raised by an adapter on any failure (auth, rate limit, network, …)."""


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete(self, model: str, system: str, messages: list[dict]) -> str:
        """messages: [{role: 'user'|'assistant', content: str}]"""
        raise NotImplementedError
