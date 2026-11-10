"""
The user-facing side of "model-agnostic": a curated catalog of models
across providers, each flagged with whether this backend currently has
a key for it. The backend already accepts any ``provider:model`` as
``model_override`` (see ``core/rag.py``) — this module is what lets
the frontend offer a real picker instead of that capability only being
reachable by hand-crafting a request body.
"""
from __future__ import annotations

from app.config import get_settings
from app.models import ModelOption

# (provider, model, display label)
_CATALOG: list[tuple[str, str, str]] = [
    ("anthropic", "claude-sonnet-4-5", "Claude Sonnet 4.5"),
    ("anthropic", "claude-haiku-4-5", "Claude Haiku 4.5"),
    ("openai", "gpt-4o-mini", "GPT-4o mini"),
    ("openai", "gpt-4o", "GPT-4o"),
    ("gemini", "gemini-1.5-flash", "Gemini 1.5 Flash"),
    ("gemini", "gemini-1.5-pro", "Gemini 1.5 Pro"),
    ("deepseek", "deepseek-chat", "DeepSeek Chat"),
    ("groq", "qwen/qwen3.8-27b", "Qwen 3.8 27B (Groq)"),
    ("groq", "openai/gpt-oss-120b", "GPT-OSS 120B (Groq)"),
]

_KEY_BY_PROVIDER = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "deepseek": "deepseek_api_key",
    "groq": "groq_api_key",
}


def list_models() -> list[ModelOption]:
    settings = get_settings()
    chain = set(settings.llm_chain)
    options = []
    for provider, model, label in _CATALOG:
        entry_id = f"{provider}:{model}"
        key_field = _KEY_BY_PROVIDER.get(provider)
        configured = bool(key_field and getattr(settings, key_field, None))
        options.append(
            ModelOption(
                id=entry_id, provider=provider, model=model, label=label,
                configured=configured, is_default_chain=entry_id in chain,
            )
        )
    return options
