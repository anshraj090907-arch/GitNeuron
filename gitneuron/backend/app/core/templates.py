"""
Template library.

The synopsis/deck describe an "open-source template library" of
production-ready agent configurations. Rather than padding this with
placeholder entries to hit a marketing number, GitNeuron ships a small
set of genuinely distinct, working templates — each one changes the
system prompt (and therefore the agent's actual behavior), not just
its label. New templates are plain Python objects: adding one is the
whole integration surface, which is what "reusable, forkable template"
means in practice.
"""
from __future__ import annotations

from app.models import Template

_TEMPLATES: dict[str, dict] = {
    "onboarding": {
        "name": "Codebase Onboarding",
        "description": "Explains structure, entry points and how pieces fit together — for a new contributor's first hour in the repo.",
        "system_suffix": (
            "You are onboarding a new developer. Prioritize the big picture: what this project does, "
            "its entry points, its major modules and how they call into each other. Prefer a short "
            "mental model over a line-by-line walkthrough, and point to specific files for depth."
        ),
    },
    "code_review": {
        "name": "Code Review Assistant",
        "description": "Reviews retrieved code for correctness, edge cases, and style against the rest of the codebase's conventions.",
        "system_suffix": (
            "You are reviewing code. Be specific and critical: note correctness issues, missed edge "
            "cases, inconsistent error handling, and places where the code diverges from patterns used "
            "elsewhere in this repository. Cite file and line for every issue you raise. If the code "
            "looks sound, say so plainly rather than inventing nitpicks."
        ),
    },
    "debugging": {
        "name": "Debugging Assistant",
        "description": "Traces how a reported symptom could originate in the retrieved code, and where to add instrumentation.",
        "system_suffix": (
            "You are helping debug an issue. Reason about how the described symptom could arise from "
            "the retrieved code: trace call paths, state mutations and assumptions that could break. "
            "Suggest concrete places to add logging or breakpoints. Be explicit when the retrieved "
            "context isn't enough to localize the bug, and say what additional file would help."
        ),
    },
    "docs": {
        "name": "Documentation Generator",
        "description": "Drafts README-style or docstring-style documentation grounded in the actual implementation.",
        "system_suffix": (
            "You are drafting documentation. Write clear, accurate prose or docstrings strictly "
            "grounded in the retrieved code — describe what it actually does, its parameters, return "
            "values and side effects, not what a typical function with that name might do."
        ),
    },
    "architecture": {
        "name": "Architecture Explainer",
        "description": "Describes system structure and data flow, and can render a diagram of it.",
        "system_suffix": (
            "You are explaining system architecture and data flow. When a diagram would clarify the "
            "relationship between components better than prose, include one as a fenced ```mermaid code "
            "block (flowchart or sequence diagram) using only names drawn from the retrieved context, "
            "and briefly explain it afterward."
        ),
    },
    "default": {
        "name": "General Q&A",
        "description": "Direct, grounded answers to any question about the repository.",
        "system_suffix": "",
    },
}


def list_templates() -> list[Template]:
    return [Template(id=tid, name=t["name"], description=t["description"]) for tid, t in _TEMPLATES.items()]


def system_suffix_for(template_id: str | None) -> str:
    return _TEMPLATES.get(template_id or "default", _TEMPLATES["default"])["system_suffix"]
