# ctxeng — Python Context Engineering Library

<p align="center">
  <strong>Stop copy-pasting files into ChatGPT.<br>
  Build the perfect LLM context from your codebase, automatically.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/ctxeng/"><img src="https://img.shields.io/pypi/v/ctxeng?color=blue&label=pypi" alt="PyPI"></a>
  <a href="https://github.com/sayeem3051/python-context-engineer/actions"><img src="https://github.com/sayeem3051/python-context-engineer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/ctxeng/"><img src="https://img.shields.io/pypi/pyversions/ctxeng" alt="Python"></a>
  <img src="https://img.shields.io/github/license/sayeem3051/python-context-engineer" alt="License">
  <img src="https://img.shields.io/pypi/dm/ctxeng?label=downloads" alt="Downloads">
</p>

---

**Context engineering** is the new prompt engineering.
The quality of your LLM's output depends almost entirely on *what you put in the context window* — not how you phrase the question.

`ctxeng` solves this automatically:

- **Scans your codebase** and scores every file for relevance to your query
- **Ranks by signal** — keyword overlap, AST symbols, git recency, import graph
- **Fits the budget** — smart truncation keeps the best parts within any model's token limit
- **Ships ready to paste** — XML, Markdown, or plain text output that works with Claude, GPT-4o, Gemini, and every other model

Zero required dependencies. Works with any LLM.

---

## Installation

```bash
pip install ctxeng
```

For accurate token counting (strongly recommended):

```bash
pip install "ctxeng[tiktoken]"
```

For one-line LLM calls:

```bash
pip install "ctxeng[anthropic]"    # Claude
pip install "ctxeng[openai]"       # GPT-4o
pip install "ctxeng[all]"          # everything
```

---

## Quickstart

### Python API

```python
from ctxeng import ContextEngine

engine = ContextEngine(root=".", model="claude-sonnet-4")
ctx = engine.build("Fix the authentication bug in the login flow")

print(ctx.summary())
# Context summary (12,340 tokens / 197,440 budget):
#   Included : 8 files
#   Skipped  : 23 files (over budget)
#   [████████  ] 0.84  src/auth/login.py
#   [███████   ] 0.71  src/auth/middleware.py
#   [█████     ] 0.53  src/models/user.py
#   [████      ] 0.41  tests/test_auth.py
#   ...

# Paste directly into your LLM
print(ctx.to_string())
```

### Fluent Builder API

```python
from ctxeng import ContextBuilder

ctx = (
    ContextBuilder(root=".")
    .for_model("gpt-4o")
    .only("**/*.py")
    .exclude("tests/**", "migrations/**")
    .from_git_diff()                        # only changed files
    .with_system("You are a senior Python engineer. Be concise.")
    .build("Refactor the payment module to use async/await")
)

print(ctx.to_string("markdown"))
```

### One-line LLM call

```python
from ctxeng import ContextEngine
from ctxeng.integrations import ask_claude

engine = ContextEngine(".", model="claude-sonnet-4")
ctx = engine.build("Why is the test_login test failing?")

response = ask_claude(ctx)
print(response)
```

### CLI

```bash
# Build context for a query and print to stdout
ctxeng build "Fix the auth bug"

# Focused on git-changed files only
ctxeng build "Review my changes" --git-diff

# Target a specific model with markdown output
ctxeng build "Refactor this" --model gpt-4o --fmt markdown

# Save to file
ctxeng build "Explain the payment flow" --output context.md

# Project stats
ctxeng info
```

---

## How It Works

```
Your codebase                    ctxeng                      Your LLM
─────────────                ────────────────            ────────────────
src/auth/login.py  ─┐
src/models/user.py ─┤  1. Score files         2. Fit budget     <context>
src/api/routes.py  ─┼─► vs query + git  ─►   smart truncate ─► <file>...</file>
tests/test_auth.py ─┤     recency + AST        token-aware       <file>...</file>
...500 more files  ─┘                                           </context>
```

### Scoring signals

Each file gets a relevance score from 0 → 1, combining:

| Signal | What it measures |
|--------|-----------------|
| **Keyword overlap** | How many query terms appear in the file content |
| **AST symbols** | Class/function/import names that match the query (Python) |
| **Path relevance** | Filename and directory names matching query tokens |
| **Git recency** | Files touched in recent commits score higher |

### Token budget optimization

Files are ranked by score and filled greedily into the token budget. Files that don't fit are **smart-truncated** (head + tail, never middle) rather than dropped entirely — the top of a file has imports and class defs; the tail has recent changes. Both are high-signal.

---

## Examples

### Debug a failing test

```python
from ctxeng import ContextBuilder
from ctxeng.integrations import ask_claude

ctx = (
    ContextBuilder(".")
    .for_model("claude-sonnet-4")
    .include_files("tests/test_payment.py", "src/payment/service.py")
    .with_system("You are a Python debugging expert.")
    .build("test_charge_user is failing with a KeyError on 'amount'")
)
response = ask_claude(ctx)
```

### Code review on a PR

```python
# Only include what changed in this branch vs main
ctx = (
    ContextBuilder(".")
    .for_model("gpt-4o")
    .from_git_diff(base="main")
    .with_system("Do a thorough code review. Flag security issues first.")
    .build("Review this pull request")
)
```

### Explain an unfamiliar codebase

```python
from ctxeng import ContextEngine

engine = ContextEngine(
    root="/path/to/project",
    model="gemini-1.5-pro",  # 1M token window → include everything
)
ctx = engine.build("Give me a high-level architecture overview")
print(ctx.to_string())
```

### Targeted refactor

```python
ctx = (
    ContextBuilder(".")
    .for_model("claude-sonnet-4")
    .only("src/database/**/*.py")
    .exclude("**/*_test.py")
    .build("Convert all raw SQL queries to use SQLAlchemy ORM")
)
```

---

## API Reference

### `ContextEngine`

```python
ContextEngine(
    root=".",               # Project root
    model="claude-sonnet-4",# Sets token budget automatically
    budget=None,            # Or explicit TokenBudget(total=50_000)
    max_file_size_kb=500,   # Skip files larger than this
    include_patterns=None,  # ["**/*.py"] — only these files
    exclude_patterns=None,  # ["tests/**"] — skip these
    use_git=True,           # Use git recency signal
)
```

```python
engine.build(
    query="",               # What you want the LLM to do
    files=None,             # Explicit list of paths (skips auto-discovery)
    git_diff=False,         # Only changed files
    git_base="HEAD",        # Diff base ref
    system_prompt="",       # System prompt (counts against budget)
    fmt="xml",              # "xml" | "markdown" | "plain"
)
# → Context
```

### `ContextBuilder` (fluent API)

```python
ContextBuilder(root=".")
    .for_model("gpt-4o")
    .with_budget(total=50_000, reserved_output=4096)
    .only("**/*.py", "**/*.yaml")
    .exclude("tests/**", "migrations/**")
    .include_files("src/specific.py")
    .from_git_diff(base="main")
    .with_system("You are an expert Python engineer.")
    .max_file_size(200)     # KB
    .no_git()
    .build("query")
# → Context
```

### `Context`

```python
ctx.to_string(fmt="xml")    # → str ready to paste into an LLM
ctx.summary()               # → human-readable summary with token counts
ctx.files                   # → list[ContextFile], sorted by relevance
ctx.skipped_files           # → files that didn't fit the budget
ctx.total_tokens            # → estimated token usage
ctx.budget.available        # → remaining token budget
```

### `TokenBudget`

```python
TokenBudget.for_model("claude-sonnet-4")  # auto-detect limit
TokenBudget(total=50_000, reserved_output=2048, reserved_system=512)
```

Supported models (auto-detected): `claude-opus-4`, `claude-sonnet-4`, `claude-haiku-4`, `gpt-4o`, `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`, `gemini-1.5-pro`, `gemini-1.5-flash`, `llama-3`.

---

## CLI Reference

```
ctxeng [--root PATH] <command> [options]

Commands:
  build   Build context for a query
  info    Show project info and file stats

build options:
  --model, -m     Target model (default: claude-sonnet-4)
  --fmt, -f       Output format: xml | markdown | plain (default: xml)
  --output, -o    Write to file instead of stdout
  --only          Glob patterns to include
  --exclude       Glob patterns to exclude
  --files         Explicit file list
  --git-diff      Only include git-changed files
  --git-base      Git base ref (default: HEAD)
  --system        System prompt text
  --budget        Override total token budget
  --no-git        Disable git recency scoring
  --max-size      Max file size in KB (default: 500)
```

---

## Supported Models

| Model | Context window | Auto-detected |
|-------|---------------|---------------|
| claude-opus-4, claude-sonnet-4, claude-haiku-4 | 200K | ✓ |
| gpt-4o, gpt-4-turbo | 128K | ✓ |
| gpt-4 | 8K | ✓ |
| gpt-3.5-turbo | 16K | ✓ |
| gemini-1.5-pro, gemini-1.5-flash | 1M | ✓ |
| llama-3 | 32K | ✓ |
| any other | 32K (safe default) | — |

---

## Why not just paste files manually?

You could. But you'll hit these problems immediately:

- **Token limit errors** — too many files, context overflows
- **Irrelevant noise** — wrong files dilute signal, hurt output quality
- **Stale context** — you forget to update when code changes
- **Manual effort** — figuring out which files matter takes time

`ctxeng` solves all four. The right files, in the right order, trimmed to fit, every time.

---

## Roadmap

- [ ] Semantic similarity scoring (optional embedding model)
- [ ] `ctxeng watch` — auto-rebuild context on file changes
- [ ] VSCode extension
- [ ] Import graph analysis (include files imported by relevant files)
- [ ] `.ctxengignore` file support
- [ ] Streaming context into LLM APIs

---

## Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/sayeem3051/python-context-engineer
cd python-context-engineer
pip install -e ".[dev]"
pytest
```

---

## License

MIT. Use freely, modify as needed, contribute back if you can.

---

<p align="center">
  If <code>ctxeng</code> saved you time, please ⭐ the repo — it helps others find it.
</p>
