# GitNeuron

Chat with any GitHub repository through natural-language conversation.
GitNeuron indexes a repository's code and documentation with
repository-aware chunking and semantic search, then grounds every
answer in the retrieved source — implementing the RAG pipeline and
feature set described in the project synopsis and presentation
(PROJECT ID 2026MCSEAIA14).

## Feature coverage

Every item below is implemented and wired end-to-end (backend → API →
UI), not stubbed.

| Synopsis / deck item | Where it lives |
|---|---|
| GitHub ingestion, with upfront validation ("repository valid and accessible?") | `backend/app/core/github_service.py` (`validate_repo`) |
| Repository-aware chunking (tree-sitter AST boundaries, structural fallback, heading-aware docs) | `backend/app/core/chunking.py` |
| Embeddings (local Sentence-Transformers, swappable) | `backend/app/core/embeddings.py` |
| Vector database (ChromaDB) | `backend/app/core/vectorstore.py` |
| Model-agnostic LLM layer: Claude, GPT, Gemini, DeepSeek, Llama/Qwen (via Groq) | `backend/app/providers/`, exposed to the UI via `GET /api/models` + `ModelSelector.tsx` |
| RAG orchestration + grounded, cited prompting | `backend/app/core/rag.py` |
| "Understands file structure" | Repo file tree captured at index time (`github_service.build_file_tree`), browsable in the UI (`FileTree.tsx`) **and** injected as condensed text into every answer's prompt, so structural questions aren't limited to whatever chunks happen to rank highest |
| **Live agent reasoning canvas** | `rag.answer_question_stream` is a generator that yields each step the instant it happens over Server-Sent Events (`POST /api/chat/stream`); the frontend renders it as a growing node graph (`ReasoningTrace.tsx`) **while the answer is still being produced**, not after the fact |
| **Autonomous error recovery** | Two independent layers: (1) LLM calls retry in-provider, then walk the configured fallback chain (`rag.py`); (2) repository ingestion falls back from `git clone` to a GitHub tarball download over HTTPS if the clone fails (`github_service.clone_or_fetch`) |
| **One-click artifact export** | GitHub Gist / PDF-with-citations / CodeSandbox (`backend/app/core/export.py`, `ExportMenu.tsx`) |
| Open-source template library | A small set of genuinely distinct system-prompt templates (Onboarding, Code Review, Debugging, Docs, Architecture) that change the agent's actual behavior, not just a label (`backend/app/core/templates.py`, `TemplateSelector.tsx`) — honestly scoped rather than padded to a marketing count |
| Generative UI | Architecture answers can render a Mermaid diagram inline (`MermaidBlock.tsx`) when the Architecture template is active |
| Voice interface | Browser speech-to-text in the composer where supported (`ChatPanel.tsx`, degrades silently elsewhere) |
| Chat interface with precise file + line citations | `ChatPanel.tsx`, `SourcesPanel.tsx` |
| Apache-2.0, model-agnostic, open-source design | `LICENSE`, `backend/app/config.py` |

## Architecture

```
GitHub repo ──validate──> clone (git) ──fails?──> tarball fallback (REST API)
                                │
                        file walk + file tree
                                │
                  chunk (tree-sitter, repo-aware) ──> embed ──> ChromaDB
                                                                    │
user question ──plan (skip retrieval for small talk)──> embed query│
                                │                                   │
                      similarity search (top-k) <───────────────────┘
                                │
              + condensed file tree + template system-prompt
                                │
         provider chain, retried then switched on failure
         (Claude → GPT → Gemini → DeepSeek → Llama/Qwen)
                                │
      live SSE stream of reasoning steps ──> grounded answer + sources
```

Indexing runs in a background thread per repository and is polled by
the frontend; chat responses stream over SSE so the reasoning canvas
fills in live rather than appearing only once the full answer is back.

## Project structure

```
gitneuron/
├── backend/
│   ├── app/
│   │   ├── main.py                   FastAPI app + route registration
│   │   ├── config.py                  Settings (env-driven, model-agnostic)
│   │   ├── models.py                  Pydantic schemas
│   │   ├── core/
│   │   │   ├── github_service.py      Validate, clone, tarball-fallback, walk, file tree
│   │   │   ├── chunking.py            Repository-aware (tree-sitter) chunking
│   │   │   ├── embeddings.py          Sentence-Transformers embedding wrapper
│   │   │   ├── vectorstore.py         ChromaDB persistence + query
│   │   │   ├── indexing.py            Background indexing pipeline + status + file tree cache
│   │   │   ├── rag.py                 Retrieval + generation + live reasoning stream
│   │   │   ├── templates.py           System-prompt template library
│   │   │   ├── model_catalog.py       Curated provider/model list + configured-key flags
│   │   │   └── export.py              Gist / PDF / CodeSandbox export
│   │   ├── providers/
│   │   │   ├── base.py                LLMProvider interface
│   │   │   └── adapters.py            Anthropic / OpenAI / Gemini / DeepSeek / Groq
│   │   └── routes/
│   │       ├── repos.py               POST /api/repos, GET .../status, GET .../files
│   │       ├── chat.py                POST /api/chat, POST /api/chat/stream (SSE)
│   │       ├── templates.py           GET /api/templates
│   │       ├── model_catalog.py       GET /api/models
│   │       └── export.py              POST /api/export/{gist,pdf,sandbox}
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx                    Top-level state: indexing, chat, model/template selection
    │   ├── components/
    │   │   ├── RepoBar.tsx             Repo URL input + live index status
    │   │   ├── FileTree.tsx            Collapsible repo file-structure explorer
    │   │   ├── ChatPanel.tsx           Message list, composer, voice input
    │   │   ├── ModelSelector.tsx       Provider/model picker (reflects configured keys)
    │   │   ├── TemplateSelector.tsx    System-prompt template picker
    │   │   ├── MessageBubble.tsx       Renders one turn (markdown + Mermaid + extras)
    │   │   ├── MermaidBlock.tsx        Inline architecture-diagram rendering
    │   │   ├── ReasoningTrace.tsx      Live-streaming reasoning node graph
    │   │   ├── SourcesPanel.tsx        Cited file/line snippets
    │   │   └── ExportMenu.tsx          Gist / PDF / CodeSandbox export
    │   ├── lib/{api.ts,types.ts}
    │   └── styles/global.css           Hand-built minimal design system
    ├── index.html
    ├── package.json
    └── vite.config.ts
```

## Running it

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set at least ONE provider key, e.g.:
#   ANTHROPIC_API_KEY=sk-ant-...
# optionally GITHUB_TOKEN for private repos / higher rate limits

uvicorn app.main:app --reload --port 8000
```

The first run downloads the local embedding model
(`sentence-transformers/all-MiniLM-L6-v2`, ~90MB) — no API key needed
for embeddings, file-tree capture, or chunking.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed URL (default `http://localhost:5173`). The dev
server proxies `/api` to `http://localhost:8000`, so both must be
running.

### 3. Use it

1. Paste a `github.com` repository URL (e.g.
   `https://github.com/pallets/flask`) and click **Index repository**.
   Watch it move through validating → cloning → chunking → embedding.
2. Once **Ready**, open **File structure** to browse what was indexed.
3. Pick a **template** (Onboarding, Code Review, Debugging, Docs,
   Architecture) and, optionally, a specific **model** — leave it on
   "Auto" to use the configured fallback chain.
4. Ask a question. The reasoning canvas fills in live (plan → embed →
   search → generate, with any retry/fallback shown) while the answer
   streams in; the finished answer shows its exact file + line sources.
5. Use **Export** on any answer to push it to a GitHub Gist, download
   it as a PDF with citations, or open it in CodeSandbox.

## Configuration reference (`backend/.env`)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `GROQ_API_KEY` | At least one, for generation — also controls which models `GET /api/models` marks as usable |
| `GITHUB_TOKEN` | Optional — private repos, higher clone/API rate limits, and the tarball-fallback path |
| `GITHUB_GIST_TOKEN` | Optional — defaults to `GITHUB_TOKEN`; needs `gist` scope |
| `EMBEDDING_MODEL` | Any Sentence-Transformers model name |
| `LLM_CHAIN` | Ordered `provider:model` fallback list, e.g. `anthropic:claude-sonnet-4-5,openai:gpt-4o-mini` |
| `TOP_K` | Chunks retrieved per question (default 8) |
| `MAX_CHUNK_TOKENS` | Target chunk size (default 400) |

## Notes on scope

This is a working reference implementation, built to run locally
without infrastructure beyond Python + Node. Every row in the feature
table is functional end-to-end. Two things are deliberately scoped
honestly rather than inflated to match the deck's language:

- **"100+ agent templates"** → a handful of templates that each
  genuinely change system behavior. Padding this to a marketing number
  with copy-pasted prompts would be worse than naming the real count.
- **Live reasoning canvas** → a real-time step graph (what the agent is
  actually doing, as it happens), not a fabricated "thoughts" narration.

Items in the synopsis's "Future Scope" (incremental re-indexing on new
commits, private-repo auth beyond a token, multi-repo comparison, IDE
integration) are intentionally left as extension points, not stubbed
in the UI.

## License

Apache-2.0, as proposed in the synopsis.
