# Changelog

## [0.1.3] — 2026-04-05

### Added

- `ctxeng.costs`: `COST_PER_1K_INPUT_TOKENS`, `estimate_cost()`, `matched_pricing_model()`
- `Context.cost_estimate` and `Context.summary(show_cost=...)` with **Est. cost** line
- CLI: `--show-cost` / `--no-show-cost` (default: show)
- Optional extra `watch`: `pip install "ctxeng[watch]"` pulls in `watchdog>=3.0` (for watch mode)
- PyPI package keywords refreshed (`import-graph`, `cost-estimation`, etc.)

## [0.1.2] — 2026-04-05

### Added

- `.ctxengignore` file support (gitignore-style patterns via pathspec)
- `pathspec>=0.12` dependency (declared install requirement)
- `parse_ctxengignore()` public API; patterns applied in filesystem collection
- Import graph analysis: `build_import_graph()`, `expand_with_imports()`
- `ContextEngine(use_import_graph=..., import_graph_depth=...)`
- `ContextBuilder.use_import_graph(depth=...)` and `no_import_graph()`
- CLI: `--import-graph` / `--no-import-graph`, `--import-graph-depth N`

### Note

[0.1.1] was tagged in git and recorded below, but **PyPI had no 0.1.1 upload**; the registry went **0.1.0 → 0.1.2**. This entry summarizes everything shipped in **0.1.2** on PyPI.

## [0.1.1] — 2026-04-05

### Added

- `.ctxengignore` file support (gitignore-style patterns via pathspec)
- `parse_ctxengignore()` public API
- Patterns applied automatically in filesystem collection

## [0.1.0] — 2026-04-05

### Added

- Initial release
- ContextEngine and ContextBuilder APIs
- AST-aware relevance scoring
- Git recency signal
- Token budget optimization with smart truncation
- Claude, OpenAI, LangChain integrations
- CLI: ctxeng build / ctxeng info
- Zero required dependencies
