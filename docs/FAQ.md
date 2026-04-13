## FAQ

### Does ctxeng send my whole repo to an LLM?
No. ctxeng selects a subset of files (or chunks with `--rag`) based on your query and token budget.

### How does redaction work?
When enabled (default), ctxeng masks common secrets and PII patterns before token counting, tracing, or output.

### What languages are supported?
- File discovery and keyword/path scoring work for many text/code files.
- Python import graph and skeleton mode are Python-specific.
- JS/TS/Go AST symbol extraction is supported via optional tree-sitter dependencies.

### Why is the VSCode extension disabled?
It is currently under development and disabled to avoid unstable activation in releases. Use the CLI/Python package.

