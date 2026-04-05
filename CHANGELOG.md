# Changelog

## [0.1.2] — 2026-04-05

### Added

- Python import graph: `build_import_graph()`, `expand_with_imports()`
- `ContextEngine(use_import_graph=..., import_graph_depth=...)`
- `ContextBuilder.use_import_graph(depth=...)` and `no_import_graph()`
- CLI: `--import-graph` / `--no-import-graph`, `--import-graph-depth N`

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
