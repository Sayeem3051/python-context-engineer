# Contributing to ctxeng

Thank you for helping make ctxeng better! This guide covers everything you need to get started.

## Development setup

```bash
git clone https://github.com/your-username/python-context-engineer
cd python-context-engineer
pip install -e ".[dev]"
```

## Running tests

```bash
pytest                          # run all tests
pytest tests/unit/              # unit tests only
pytest -k "test_scoring"        # filter by name
pytest --cov=ctxeng             # with coverage
```

## Code style

We use `ruff` for linting:

```bash
ruff check ctxeng/
ruff format ctxeng/
```

## Project layout

```
ctxeng/
├── __init__.py         Public API exports
├── core.py             ContextEngine main class
├── builder.py          ContextBuilder fluent API
├── models.py           Data classes (Context, ContextFile, TokenBudget)
├── scorer.py           File relevance scoring (keyword, AST, git, path)
├── optimizer.py        Token counting, budget fitting, smart truncation
├── cli.py              CLI entry point
├── sources/            File collectors (filesystem, git, explicit)
└── integrations/       LLM client helpers (Claude, OpenAI, LangChain)
```

## How to add a new scoring signal

1. Add a function `_my_signal_score(content, query, ...) -> float` in `scorer.py`
2. Call it from `score_file()` and add it to the weighted average
3. Add a unit test in `tests/unit/test_core.py`
4. Document it in the README scoring table

## How to add a new LLM integration

1. Add an `ask_mymodel(ctx, ...) -> str` function in `ctxeng/integrations/__init__.py`
2. Follow the pattern of `ask_claude` / `ask_openai`
3. Add it to `pyproject.toml` optional-dependencies
4. Document it in the README

## Submitting a PR

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Write code + tests
3. Run `pytest` and `ruff check` — both must pass
4. Open a PR with a clear description of what it does and why

## Reporting bugs

Open an issue with:
- Python version
- `ctxeng` version
- Minimal reproduction case
- Expected vs actual behavior
