## FAQ

### Why ctxeng vs Cursor / Copilot?

Cursor and Copilot are great for **in-editor assistance**. `ctxeng` focuses on a different problem: building a **portable**, **budget-safe**, **reproducible** context bundle you can use with *any* LLM (chat UI, API, CI).

`ctxeng` is especially useful when you need:

- deterministic selection (ranked evidence, not “whatever is open”)
- strict token budgeting (fits the model window)
- safety (redaction before output/traces)
- large-repo workflows (RAG chunk retrieval)
- automation (CI, snapshots, tracing)

### Does ctxeng send my whole repo to an LLM?

No. ctxeng selects a subset of files (or chunks with `--rag`) based on your query and token budget.

Also: **ctxeng itself does not call an LLM** unless you use an optional integration function (e.g. `ask_claude()`).

### How does redaction work?

When enabled (default), ctxeng masks common secrets and PII patterns before token counting, tracing, or output.

To disable:

```bash
ctxeng build "Your query" --no-redact
```

### What languages are supported?

- **Discovery + keyword/path scoring**: works for many text/code files.
- **Python-only features**:
  - import graph expansion
  - skeleton mode
- **JS/TS/Go symbols**: supported via optional tree-sitter dependencies:

```bash
pip install "ctxeng[ast]"
```

### Why is the VSCode extension disabled?

It is currently under development and disabled to avoid unstable activation in releases. Use the CLI/Python package.

### I got `Token required because branch is protected` from Codecov

That usually means Codecov requires a token for uploads on protected branches.

Fix:

- Add `CODECOV_TOKEN` in your GitHub repo secrets
- Or configure Codecov to allow tokenless uploads for your setup

### PyPI upload problems

#### `No module named twine`

Install it in the environment you’re using:

```bash
python -m pip install -U twine build
```

#### `HTTPError: 400 Bad Request` on upload

Most common causes:

- that version already exists on PyPI
- you’re uploading old artifacts from `dist/`

Recommended flow:

```bash
rm -rf dist build
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

### “It feels overwhelming—where do I start?”

Start with the smallest workflow:

```bash
pip install ctxeng
ctxeng build "Fix the auth bug" --git-diff --fmt markdown --output ctx.md
```

Paste `ctx.md` into your LLM. Add `--trace` once you want explainability, and `--rag` once your repo is large.

