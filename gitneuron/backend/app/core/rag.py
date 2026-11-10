"""
RAG orchestration: plan → retrieve → generate, walking the configured
provider chain (with an in-provider retry before switching models) so
a rate-limited or failing model doesn't surface as a dead end to the
user — the "autonomous error recovery" feature from the synopsis.

``answer_question_stream`` is a generator that yields each
``ReasoningStep`` the instant it happens, which is what lets the
frontend render a *live* agent reasoning canvas instead of a trace
that only appears after the full answer is already done.
"""
from __future__ import annotations

import re
import time
import uuid
from typing import Generator

from app.config import get_settings
from app.core import indexing, vectorstore
from app.core.embeddings import embed_query
from app.core.templates import system_suffix_for
from app.providers.adapters import get_provider
from app.providers.base import ProviderError
from app.models import ChatResponse, ReasoningStep, SourceChunk

BASE_SYSTEM_PROMPT = """You are GitNeuron, an assistant that explains a specific GitHub repository.
Answer ONLY using the provided code/documentation context. If the context does not contain
the answer, say so plainly instead of guessing. When you reference code, name the exact file
and, where useful, the function or class. Keep answers precise and grounded; do not invent
file names, functions, or behavior that isn't shown in the context."""

# Small-talk GitNeuron can answer without spending a retrieval + generation
# round trip on vector search — a minimal version of the "selective
# retrieval" idea from the literature survey (Repoformer, Wu et al. 2024):
# not every turn needs the repository pulled in.
_SMALL_TALK_RE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|cool|great|nice|yo)[.!?\s]*$", re.IGNORECASE
)

RETRIES_PER_PROVIDER = 2


def _step(label: str, kind: str, detail: str = "", status: str = "done") -> ReasoningStep:
    return ReasoningStep(id=str(uuid.uuid4())[:8], label=label, kind=kind, detail=detail, status=status)


def _build_context(hits: list[dict], max_chars: int = 12000) -> str:
    blocks = []
    total = 0
    for h in hits:
        block = (
            f"### {h['file_path']} (lines {h['start_line']}-{h['end_line']})\n```{h['language']}\n{h['text']}\n```"
        )
        if total + len(block) > max_chars and blocks:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)


def answer_question_stream(
    repo_id: str, question: str, history: list[dict],
    model_override: str | None, template_id: str | None,
) -> Generator[dict, None, None]:
    """
    Yields {"type": "step", "step": ReasoningStep} as each stage happens,
    then exactly one {"type": "final", "response": ChatResponse}.
    """
    settings = get_settings()

    plan_step = _step("Plan", "plan", detail="Deciding whether retrieval is needed", status="running")
    yield {"type": "step", "step": plan_step}

    needs_retrieval = not _SMALL_TALK_RE.match(question.strip())
    plan_step.status = "done"
    plan_step.detail = "Retrieval needed" if needs_retrieval else "Small talk — skipping retrieval"
    yield {"type": "step", "step": plan_step}

    hits: list[dict] = []
    if needs_retrieval:
        embed_step = _step("Embed query", "retrieval", detail=question[:120], status="running")
        yield {"type": "step", "step": embed_step}
        query_vec = embed_query(question)
        embed_step.status = "done"
        yield {"type": "step", "step": embed_step}

        search_step = _step("Similarity search", "retrieval", detail=f"top_k={settings.top_k}", status="running")
        yield {"type": "step", "step": search_step}
        hits = vectorstore.query(repo_id, query_vec, settings.top_k)
        search_step.status = "done"
        search_step.detail = f"{len(hits)} candidate chunks"
        yield {"type": "step", "step": search_step}

        if hits:
            retrieved_step = _step(
                f"Retrieved {len(hits)} relevant chunks", "retrieval",
                detail=", ".join(sorted({h['file_path'] for h in hits}))[:200],
            )
            yield {"type": "step", "step": retrieved_step}

    if needs_retrieval and not hits:
        fail_step = _step("No indexed content matched", "error", status="failed")
        yield {"type": "step", "step": fail_step}
        yield {
            "type": "final",
            "response": ChatResponse(
                answer="This repository doesn't appear to be indexed yet, or no relevant code was found "
                       "for that question. Try indexing it first, or rephrase your question.",
                sources=[], reasoning=[], model_used="none",
            ),
        }
        return

    sources = [
        SourceChunk(
            file_path=h["file_path"], start_line=h["start_line"], end_line=h["end_line"],
            language=h["language"], snippet=h["text"][:600], score=round(h["score"], 4),
        )
        for h in hits
    ]

    # The file tree is loaded for every substantive question, not just ones
    # that look structural — it's what actually lets GitNeuron answer "what
    # does this repo's structure look like?" correctly instead of guessing
    # from whichever chunks happened to rank highest for that query.
    tree_text = None
    if needs_retrieval:
        tree_step = _step("Load repository map", "tool", status="running")
        yield {"type": "step", "step": tree_step}
        tree_text = indexing.get_file_tree_text(repo_id, max_lines=60)
        tree_step.status = "done"
        tree_step.detail = f"{len(tree_text.splitlines())} entries" if tree_text else "unavailable"
        yield {"type": "step", "step": tree_step}

    system_prompt = BASE_SYSTEM_PROMPT
    suffix = system_suffix_for(template_id)
    if suffix:
        system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{suffix}"
    if tree_text:
        system_prompt += (
            "\n\nRepository file structure (for questions about layout, organization, "
            f"or where something lives):\n{tree_text}"
        )

    if hits:
        context = _build_context(hits)
        user_turn = (
            f"Repository context:\n\n{context}\n\n---\n\nConversation so far is provided separately. "
            f"Question: {question}"
        )
    else:
        user_turn = question

    messages = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    messages.append({"role": "user", "content": user_turn})

    chain = [model_override] if model_override else settings.llm_chain
    last_error: str | None = None

    for entry in chain:
        provider_name, _, model_name = entry.partition(":")
        provider = get_provider(provider_name)

        for attempt in range(1, RETRIES_PER_PROVIDER + 1):
            label = f"Generate with {entry}" + (f" (retry {attempt - 1})" if attempt > 1 else "")
            gen_step = _step(label, "generation", status="running")
            yield {"type": "step", "step": gen_step}
            try:
                answer_text = provider.complete(model_name, system_prompt, messages)
                gen_step.status = "done"
                yield {"type": "step", "step": gen_step}
                yield {
                    "type": "final",
                    "response": ChatResponse(answer=answer_text, sources=sources, reasoning=[], model_used=entry),
                }
                return
            except ProviderError as exc:
                gen_step.status = "failed"
                gen_step.detail = str(exc)
                yield {"type": "step", "step": gen_step}
                last_error = str(exc)
                if attempt < RETRIES_PER_PROVIDER:
                    retry_step = _step(f"Retrying {entry}", "fallback", detail="transient failure, retrying")
                    yield {"type": "step", "step": retry_step}
                    time.sleep(0.4)

        if entry != chain[-1]:
            switch_step = _step(f"Switching model away from {entry}", "fallback", detail=last_error or "")
            yield {"type": "step", "step": switch_step}

    error_step = _step("All providers failed", "error", status="failed", detail=last_error or "unknown error")
    yield {"type": "step", "step": error_step}
    yield {
        "type": "final",
        "response": ChatResponse(
            answer="I couldn't reach any configured language model provider after retrying each one. "
                   "Check that at least one API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, "
                   "DEEPSEEK_API_KEY or GROQ_API_KEY) is set in the backend's .env file.",
            sources=sources, reasoning=[], model_used="none",
        ),
    }


def answer_question(
    repo_id: str, question: str, history: list[dict],
    model_override: str | None, template_id: str | None = None,
) -> ChatResponse:
    """Non-streaming convenience wrapper — drains the stream and attaches the full trace."""
    steps: list[ReasoningStep] = []
    final: ChatResponse | None = None
    for event in answer_question_stream(repo_id, question, history, model_override, template_id):
        if event["type"] == "step":
            steps.append(event["step"])
        else:
            final = event["response"]
    assert final is not None
    final.reasoning = steps
    return final
