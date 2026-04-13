"""AST-based skeleton summaries (Python)."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Skeleton:
    text: str
    symbol_count: int


def python_skeleton(source: str) -> Skeleton:
    """
    Build a high-level outline of a Python module using the AST.

    Output includes:
    - imports (module-level)
    - class names + method signatures
    - function signatures
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return Skeleton(text="# [ctxeng:skeleton] (invalid python; skipping)\n", symbol_count=0)

    lines: list[str] = ["# [ctxeng:skeleton]", ""]
    symbol_count = 0

    def fmt_args(args: ast.arguments) -> str:
        parts: list[str] = []
        for a in getattr(args, "posonlyargs", []):
            parts.append(a.arg)
        if getattr(args, "posonlyargs", []):
            parts.append("/")
        for a in args.args:
            parts.append(a.arg)
        if args.vararg:
            parts.append("*" + args.vararg.arg)
        for a in args.kwonlyargs:
            parts.append(a.arg)
        if args.kwarg:
            parts.append("**" + args.kwarg.arg)
        return ", ".join(parts)

    # Imports
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                lines.append(f"import {a.name}")
                symbol_count += 1
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = ", ".join(a.name for a in node.names)
            dots = "." * node.level if getattr(node, "level", 0) else ""
            prefix = f"from {dots}{mod} import " if (dots or mod) else "from  import "
            lines.append(prefix + names)
            symbol_count += 1

    if symbol_count:
        lines.append("")

    # Definitions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            lines.append(f"{async_prefix}def {node.name}({fmt_args(node.args)}): ...")
            symbol_count += 1
        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)
                else:
                    bases.append("...")
            base_str = f"({', '.join(bases)})" if bases else ""
            lines.append(f"class {node.name}{base_str}:")
            symbol_count += 1
            methods = [
                n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if not methods:
                lines.append("  ...")
            else:
                for m in methods:
                    async_prefix = "async " if isinstance(m, ast.AsyncFunctionDef) else ""
                    lines.append(f"  {async_prefix}def {m.name}({fmt_args(m.args)}): ...")
                    symbol_count += 1
            lines.append("")

    return Skeleton(text="\n".join(lines).rstrip() + "\n", symbol_count=symbol_count)

