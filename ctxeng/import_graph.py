"""Static import graph for Python files under a project root."""

from __future__ import annotations

import ast
from pathlib import Path

from ctxeng.models import ContextFile
from ctxeng.optimizer import detect_language


def _normalize_path(root: Path, path: Path) -> Path:
    """Return ``path`` as a path relative to ``root`` (resolved)."""
    root = root.resolve()
    if path.is_absolute():
        try:
            return path.resolve().relative_to(root)
        except ValueError:
            return Path(path.as_posix().lstrip("/"))
    rel = (root / path).resolve()
    try:
        return rel.relative_to(root)
    except ValueError:
        return path


def _relative_to_root(root: Path, abs_path: Path) -> Path | None:
    try:
        return abs_path.resolve().relative_to(root.resolve())
    except ValueError:
        return None


def _module_paths_under_root(root: Path, parts: tuple[str, ...]) -> list[Path]:
    """Paths relative to ``root`` for ``parts`` as ``mod.py`` or ``mod/__init__.py``."""
    if not parts:
        return []
    out: list[Path] = []
    base = root.joinpath(*parts)
    py = base.with_suffix(".py")
    if py.is_file():
        rel = _relative_to_root(root, py)
        if rel is not None:
            out.append(rel)
    init = base / "__init__.py"
    if init.is_file():
        rel = _relative_to_root(root, init)
        if rel is not None:
            out.append(rel)
    return out


def _resolve_under_anchor(anchor: Path, root: Path, parts: tuple[str, ...]) -> list[Path]:
    """Resolve ``parts`` as a module under directory ``anchor`` (absolute)."""
    if not parts:
        return []
    out: list[Path] = []
    base = anchor.joinpath(*parts)
    py = base.with_suffix(".py")
    if py.is_file():
        rel = _relative_to_root(root, py)
        if rel is not None:
            out.append(rel)
    init = base / "__init__.py"
    if init.is_file():
        rel = _relative_to_root(root, init)
        if rel is not None:
            out.append(rel)
    return out


def _package_dir_for_module(root: Path, mod_rel: Path) -> Path:
    """Directory that contains submodules for a resolved module file."""
    abs_m = (root / mod_rel).resolve()
    if mod_rel.name == "__init__.py":
        return abs_m.parent
    return abs_m.parent


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = p.as_posix()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _from_import_targets(
    root: Path,
    file_rel: Path,
    module: str | None,
    names: list[str],
    level: int,
) -> list[Path]:
    """Resolve ``from ... import ...`` to existing project files."""
    targets: list[Path] = []
    root_r = root.resolve()
    abs_file = (root_r / file_rel).resolve()
    anchor = abs_file.parent
    if level > 0:
        for _ in range(level - 1):
            parent = anchor.parent
            if parent == anchor:
                break
            anchor = parent
        if not str(anchor.resolve()).startswith(str(root_r)):
            return []

    if level == 0 and module:
        mod_parts = tuple(module.split("."))
        for name in names:
            if name == "*":
                continue
            targets.extend(_module_paths_under_root(root, mod_parts + (name,)))
        return _dedupe_paths(targets)

    if module:
        mod_parts = tuple(module.split("."))
        bases = _resolve_under_anchor(anchor, root, mod_parts)
    else:
        bases = []

    if not bases and module is None and level > 0:
        for name in names:
            if name == "*":
                continue
            targets.extend(_resolve_under_anchor(anchor, root, (name,)))
        return _dedupe_paths(targets)

    for name in names:
        if name == "*":
            continue
        for base_rel in bases:
            pkg_dir = _package_dir_for_module(root, base_rel)
            targets.extend(_resolve_under_anchor(pkg_dir, root, (name,)))
        if not bases and level > 0 and module:
            targets.extend(_resolve_under_anchor(anchor, root, mod_parts + (name,)))

    return _dedupe_paths(targets)


def _import_targets(root: Path, file_rel: Path, node: ast.AST) -> list[Path]:
    targets: list[Path] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            parts = tuple(alias.name.split("."))
            targets.extend(_module_paths_under_root(root, parts))
    elif isinstance(node, ast.ImportFrom):
        targets.extend(
            _from_import_targets(
                root,
                file_rel,
                node.module,
                [a.name for a in node.names],
                node.level,
            )
        )
    return targets


def build_import_graph(root: Path, files: list[Path]) -> dict[Path, list[Path]]:
    """
    Parse each ``.py`` file and map it to other project files it imports.

    Only edges to files present in ``files`` are kept. Relative imports are
    resolved from the importing file. Stdlib and third-party imports are omitted.

    Args:
        root: Project root directory.
        files: Paths relative to ``root`` (as returned by collectors).

    Returns:
        Mapping from normalized relative path → list of imported relative paths.
    """
    root = root.resolve()
    file_set = {_normalize_path(root, f) for f in files}
    graph: dict[Path, list[Path]] = {}

    for f in files:
        if f.suffix != ".py":
            continue
        nf = _normalize_path(root, f)
        abs_py = root / nf
        try:
            text = abs_py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            graph[nf] = []
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            graph[nf] = []
            continue

        seen: set[str] = set()
        edges: list[Path] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for t in _import_targets(root, nf, node):
                    nt = _normalize_path(root, t)
                    if nt in file_set:
                        key = nt.as_posix()
                        if key not in seen:
                            seen.add(key)
                            edges.append(nt)
        graph[nf] = edges

    return graph


def expand_with_imports(
    relevant_files: list[ContextFile],
    import_graph: dict[Path, list[Path]],
    root: Path,
    max_depth: int = 1,
    score_decay: float = 0.7,
) -> list[ContextFile]:
    """
    Add files imported by high-scoring files, with decayed relevance scores.

    Does not add duplicates (paths already present keep the higher score).
    Reads file contents from disk under ``root`` for newly added paths.

    Args:
        relevant_files: Ranked context files from scoring.
        import_graph: Output of :func:`build_import_graph`.
        root: Project root for reading newly included files.
        max_depth: How many hops to follow (1 = direct imports only).
        score_decay: Each hop multiplies the parent file's score by this factor.

    Returns:
        Merged list sorted by ``relevance_score`` descending.
    """
    root = root.resolve()

    def norm(p: Path) -> Path:
        return _normalize_path(root, p)

    by_path: dict[str, ContextFile] = {}
    for cf in relevant_files:
        k = norm(cf.path).as_posix()
        if k not in by_path or cf.relevance_score > by_path[k].relevance_score:
            by_path[k] = cf

    wave = list(by_path.values())
    for _ in range(max_depth):
        next_wave: list[ContextFile] = []
        for cf in wave:
            key = norm(cf.path)
            for imp in import_graph.get(key, []):
                ik = norm(imp).as_posix()
                if ik in by_path:
                    continue
                new_score = cf.relevance_score * score_decay
                try:
                    content = (root / imp).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if not content.strip():
                    continue
                new_cf = ContextFile(
                    path=Path(imp.as_posix()),
                    content=content,
                    relevance_score=new_score,
                    language=detect_language(imp),
                    inclusion_reason="import_graph",
                )
                by_path[ik] = new_cf
                next_wave.append(new_cf)
        wave = next_wave

    return sorted(by_path.values(), key=lambda f: f.relevance_score, reverse=True)
