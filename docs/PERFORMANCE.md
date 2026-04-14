## Performance & scaling

This doc explains the biggest performance levers in `ctxeng`, what they cost, and how to keep runs fast on large repositories.

## Mental model (where time goes)

Most runtime is spent in one of these stages:

- **Discovery**: walking the filesystem + reading files
- **Scoring**: keyword/path/AST/git signals per file
- **(Optional) semantic scoring**: embeddings compute + cache IO
- **(Optional) RAG**: chunking + retrieval over top-ranked candidates
- **Budgeting**: token counting + truncation decisions

The single best optimization is shrinking the **candidate set** early.

## Fast-start checklist

- Use `.ctxengignore` to exclude heavy directories:
  - `node_modules/`, `dist/`, `build/`, `coverage/`, `venv/`, `.venv/`, logs, generated assets
- Prefer `--git-diff` for PR reviews (small candidate set).
- Disable slow signals if you don’t need them:
  - `--no-git` if git commands are slow/unavailable
  - `--no-import-graph` if import expansion isn’t useful for your task
- Use `--rag` for big repos when whole-file context is too large or too noisy.

## Scaling patterns (choose one)

### Pattern A: PR review (fastest)

```bash
ctxeng build "Review these changes. Focus on security and correctness." --git-diff --fmt markdown --output ctx.md
```

Why it’s fast: discovery is limited to the diff.

### Pattern B: Large repo explanation (accurate)

```bash
ctxeng build "Explain the authentication flow end-to-end" --rag --trace --fmt markdown --output ctx.md
```

Why it works: rank files first, then retrieve only the best chunks.

### Pattern C: High-level overview (cheap tokens)

```bash
ctxeng build "Give me a high-level architecture overview" --skeleton --fmt markdown --output ctx.md
```

Why it works: skeleton mode reduces token cost dramatically for Python.

## Parallel scoring

For large repositories, `ctxeng` can parallelize file scoring to improve throughput (scoring is CPU + IO bound).

Tips:

- Parallelism helps most when:
  - you have many medium-sized text files
  - your disk is reasonably fast (SSD)
- Parallelism helps least when:
  - the run is dominated by a few huge files (excluded by default size guard)
  - the repo is on a slow network filesystem

## Semantic scoring (optional)

Semantic scoring uses local embeddings and is optional:

```bash
pip install "ctxeng[semantic]"
```

Notes:

- Default semantic model is **`all-mpnet-base-v2`** (good quality, heavier than mini models).
- Embeddings are cached under **`.ctxeng_cache/`** keyed by `(content hash + model name)`.
- On very large repos, semantic scoring can dominate runtime; consider:
  - using `--git-diff`
  - enabling `--rag` so only top candidates are embedded/chunked
  - disabling semantic for quick iterations

## RAG performance knobs

RAG performance is mostly controlled by:

- **candidate set size**: internally bounded (top-ranked files)
- **chunk size**: `--rag-chunk-max-lines`
- **overlap**: `--rag-chunk-overlap`
- **max chunks output**: `--rag-max-chunks`

Rules of thumb:

- If output is too big/noisy: reduce `--rag-max-chunks`
- If retrieval misses key details: increase `--rag-max-chunks` or reduce `--rag-chunk-max-lines`
- If chunks lack local context: increase `--rag-chunk-context-lines`

## Token counting performance

Token counting uses `tiktoken` when installed (recommended):

```bash
pip install "ctxeng[tiktoken]"
```

Without it, ctxeng uses a fast heuristic; it’s cheaper but less accurate.

## Profiling and debugging slow runs

- Use `--trace` to see stage-level decisions and counts.
- If a run feels slow, first answer:
  - How many files were discovered?
  - Is semantic scoring enabled?
  - Is git recency enabled?
  - Is RAG enabled?

## Benchmarks template

Target: **< 5 seconds for 10K files** on a modern laptop (varies with disk + git + semantic).

Suggested benchmark scenarios:

- **PR review**: `--git-diff`
- **Large repo explain**: `--rag`
- **Overview**: `--skeleton`

Record:

- repo size (files scanned)
- flags used
- wall-clock time
- output size (included files/chunks, tokens)
