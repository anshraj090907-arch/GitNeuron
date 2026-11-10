"""
One thin adapter per model provider, all exposing the same
``complete(model, system, messages) -> str`` call. This is what makes
GitNeuron model-agnostic: the RAG layer never knows which provider it
is talking to, only that it asked for "anthropic:claude-sonnet-4-5" or
"groq:llama-3.3-70b-versatile" and got text back.
"""
from __future__ import annotations

from app.config import get_settings
from app.providers.base import LLMProvider, ProviderError


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def complete(self, model: str, system: str, messages: list[dict]) -> str:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ProviderError("ANTHROPIC_API_KEY not configured")
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            resp = client.messages.create(
                model=model,
                system=system,
                max_tokens=1500,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            )
            return "".join(block.text for block in resp.content if block.type == "text")
        except Exception as exc:  # noqa: BLE001 — surfaced uniformly to the caller
            raise ProviderError(f"Anthropic call failed: {exc}") from exc


class OpenAIProvider(LLMProvider):
    name = "openai"

    def complete(self, model: str, system: str, messages: list[dict]) -> str:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY not configured")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=model,
                max_tokens=1500,
                messages=[{"role": "system", "content": system}] +
                         [{"role": m["role"], "content": m["content"]} for m in messages],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            raise ProviderError(f"OpenAI call failed: {exc}") from exc


class GeminiProvider(LLMProvider):
    name = "gemini"

    def complete(self, model: str, system: str, messages: list[dict]) -> str:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ProviderError("GEMINI_API_KEY not configured")
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            gmodel = genai.GenerativeModel(model, system_instruction=system)
            history = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
                       for m in messages[:-1]]
            chat = gmodel.start_chat(history=history)
            resp = chat.send_message(messages[-1]["content"])
            return resp.text or ""
        except Exception as exc:
            raise ProviderError(f"Gemini call failed: {exc}") from exc


class OpenAICompatibleProvider(LLMProvider):
    """Covers DeepSeek, Groq (Llama / Qwen) and any other OpenAI-schema endpoint."""

    def __init__(self, name: str, base_url: str, api_key: str | None):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key

    def complete(self, model: str, system: str, messages: list[dict]) -> str:
        if not self.api_key:
            raise ProviderError(f"{self.name.upper()}_API_KEY not configured")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            resp = client.chat.completions.create(
                model=model,
                max_tokens=1500,
                messages=[{"role": "system", "content": system}] +
                         [{"role": m["role"], "content": m["content"]} for m in messages],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            raise ProviderError(f"{self.name} call failed: {exc}") from exc


def get_provider(name: str) -> LLMProvider:
    settings = get_settings()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai":
        return OpenAIProvider()
    if name == "gemini":
        return GeminiProvider()
    if name == "deepseek":
        return OpenAICompatibleProvider("deepseek", "https://api.deepseek.com", settings.deepseek_api_key)
    if name == "groq":
        return OpenAICompatibleProvider("groq", "https://api.groq.com/openai/v1", settings.groq_api_key)
    raise ProviderError(f"Unknown provider: {name}")
