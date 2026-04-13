"""Multi-language AST symbol extraction (optional)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AstSymbols:
    symbols: set[str]
    language: str


def extract_symbols(code: str, *, language: str) -> AstSymbols:
    """
    Extract a set of identifier-like symbols for a given language using tree-sitter.

    Supported languages (when optional deps are installed):
    - javascript
    - typescript
    - go

    If tree-sitter isn't available or language unsupported, returns empty set.
    """
    try:
        from tree_sitter_languages import get_parser  # type: ignore
    except Exception:
        return AstSymbols(symbols=set(), language=language)

    lang = language.lower().strip()
    if lang in {"js", "jsx"}:
        lang = "javascript"
    if lang in {"ts", "tsx"}:
        lang = "typescript"
    if lang not in {"javascript", "typescript", "go"}:
        return AstSymbols(symbols=set(), language=language)

    try:
        parser = get_parser(lang)
    except Exception:
        return AstSymbols(symbols=set(), language=language)

    src = code.encode("utf-8", errors="replace")
    tree = parser.parse(src)

    out: set[str] = set()

    def text(node) -> str:
        return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def add_name(n) -> None:
        if n is None:
            return
        s = text(n).strip()
        if not s:
            return
        out.add(s.lower())

    stack = [tree.root_node]
    while stack:
        node = stack.pop()

        t = node.type
        if lang in {"javascript", "typescript"} and (
            t in {"function_declaration", "class_declaration", "method_definition", "interface_declaration", "type_alias_declaration"}
        ) or lang == "go" and t in {"function_declaration", "method_declaration", "type_spec"}:
            add_name(node.child_by_field_name("name"))

        # generic identifiers (helps when above rules miss)
        if t in {"identifier", "type_identifier", "property_identifier"}:
            add_name(node)

        stack.extend(node.children)

    return AstSymbols(symbols=out, language=lang)

