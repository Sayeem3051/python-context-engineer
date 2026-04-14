## Architecture

`ctxeng` is a local-first “context compiler”: it **discovers** code, **scores** it against your task, optionally **expands/retrieves** more relevant neighbors, then **budgets + renders** a paste-ready context bundle.

```mermaid
flowchart TD
  subgraph Inputs
    Q[Task / query]
    R[(Repository root)]
    O[Options / flags]
  end

  subgraph Pipeline
    D[Discover files]
    S[Score + rank]
    IG[Import-graph expansion (optional)]
    RAG[RAG chunk retrieval (optional)]
    SK[AST skeleton (optional)]
    RX[Redact secrets + PII (optional, default on)]
    B[Fit token budget]
    RND[Render output<br/>(XML / Markdown / plain)]
  end

  Q --> S
  R --> D --> S --> IG --> RAG --> SK --> RX --> B --> RND
  O --> D
  O --> S
  O --> IG
  O --> RAG
  O --> SK
  O --> RX
  O --> B
  RND --> OUT[Context output + metadata]
```

## Key design goals

- **Deterministic & explainable**: scoring signals are explicit; optional tracing records “what was included and why”.
- **Portable**: output is not tied to any editor or model vendor (works with chat UIs, APIs, CI).
- **Budget-safe**: context is constructed to fit a specific model window (or explicit `--budget`).
- **Safety by default**: redaction runs before token counting, tracing, and rendering.

## Components (where the logic lives)

- **Discovery / sources**: `ctxeng/sources/__init__.py`
  - `collect_filesystem()`: walks the repo and yields `(path, content)`
  - `collect_git_changed()`: yields changed files (`--git-diff`)
  - `collect_explicit()`: yields exact paths (`--files` / `include_files()`)
- **Ignore rules**: `ctxeng/ignore.py`
  - merges `.gitignore` + `.ctxengignore` into a single matcher (gitwildmatch via `pathspec`)
- **Scoring / ranking**: `ctxeng/scorer.py`
  - combines signals into a score in \([0, 1]\)
  - supports optional semantic scoring + multi-language AST symbol overlap
  - supports configurable scoring weights (`.ctxeng/config.json` / `--scoring-config`)
- **Import graph expansion (Python)**: `ctxeng/import_graph.py`
  - builds a static import graph among discovered `.py` files
  - expands context with imported neighbors (with score decay) before budgeting
- **Chunking + retrieval (RAG)**: `ctxeng/chunking.py`, `ctxeng/retrieval.py`
  - splits files into overlapping chunks
  - lexical retrieval is always available; embeddings retrieval requires `ctxeng[semantic]`
- **Skeleton mode (Python)**: `ctxeng/ast_skeleton.py`
  - replaces Python bodies with an AST-derived outline for “overview” requests
- **Redaction**: `ctxeng/redaction.py`
  - masks secrets + PII with stable hashes so traces and output don’t leak sensitive values
- **Budgeting + truncation**: `ctxeng/optimizer.py`
  - estimates token counts (uses `tiktoken` if installed, otherwise heuristic)
  - greedily fills budget by score, smart-truncates large files
- **Tracing (optional)**: `ctxeng/tracing.py`
  - writes JSONL events under `.ctxeng/traces/` (safe payloads)
- **Snapshots (optional)**: `ctxeng/snapshots.py`
  - writes `context.txt` + `manifest.json` under `.ctxeng/snapshots/<id>/`
- **Orchestration**: `ctxeng/core.py`
  - `ContextEngine.build()` coordinates the whole pipeline
- **Fluent API**: `ctxeng/builder.py`
  - `ContextBuilder` provides a chainable configuration layer

## Pipeline, step-by-step

### 1) Discover files

Discovery chooses the candidate set:

- **Filesystem** (default): walk from repo root, apply ignore rules, skip binary-ish files, apply size guard.
- **Git diff** (`--git-diff`): only changed/untracked files (great for PR reviews).
- **Explicit files** (`--files` / `include_files()`): bypass discovery, useful for targeted tasks.

### 2) Score + rank

Each file is scored using a weighted mix of signals, then sorted descending. Signals include:

- **Keyword overlap**: query token overlap with content
- **Path relevance**: filename + directory names matching query tokens
- **AST symbol overlap**:
  - Python (built-in)
  - JS/TS/Go (optional, tree-sitter)
- **Git recency**: recently changed files get a boost (optional)
- **Semantic similarity**: optional local embeddings (`sentence-transformers`)

Weights can be customized with `--scoring-config` (or `.ctxeng/config.json`).

### 3) Import graph expansion (optional, Python)

If enabled, ctxeng can pull in locally imported Python modules from the discovered set (with score decay). This helps with “function is defined elsewhere” cases.

### 4) RAG chunk retrieval (optional)

For large repos, `--rag` switches from whole-file inclusion to chunk-level selection:

- Candidate set: top-ranked files are chunked (keeps runtime bounded).
- Retrieval:
  - embeddings (if installed) or lexical fallback (always available)
- Output:
  - retrieved chunks become the “ranked list” fed into budgeting

### 5) Skeleton mode (optional, Python)

`--skeleton` replaces Python file bodies with an AST-derived outline (imports, defs, methods). This is best for:

- “high-level architecture overview”
- “what are the key modules/classes?”
- tight budgets where full bodies are too expensive

### 6) Redaction (optional, default on)

Redaction runs **before** token counting, tracing, and rendering.

This is intentional: it prevents accidental leakage through:

- output text
- trace logs
- token counting artifacts

### 7) Fit token budget

Budgeting includes:

- counting query/system tokens
- greedily including top-ranked items
- smart truncation (head + tail) when a file is too large

### 8) Render output

Context is rendered as:

- `xml` (default)
- `markdown`
- `plain`

Metadata may include trace/snapshot ids and other build details.

## Practical recipes

### PR review (fast + focused)

```bash
ctxeng build "Review this PR. Focus on security and correctness." --git-diff --fmt markdown --output ctx.md
```

### Large repo explanation (RAG + tracing)

```bash
ctxeng build "Explain the authentication flow end-to-end" --rag --trace --fmt markdown --output ctx.md
```

### High-level overview (skeleton)

```bash
ctxeng build "Give me a high-level architecture overview" --skeleton --fmt markdown --output ctx.md
```

