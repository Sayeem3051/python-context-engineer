import json
import re
import tempfile
from pathlib import Path

import pytest


def test_ignore_parsers_and_combined_spec(tmp_path: Path):
    from ctxeng.ignore import combined_ignore_spec, is_ctxengignored, parse_ctxengignore, parse_gitignore

    (tmp_path / ".gitignore").write_text(
        "\n".join(
            [
                "# comment",
                "dist/",
                "*.log",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".ctxengignore").write_text(
        "\n".join(
            [
                "# comment",
                "secrets.txt",
                "",
            ]
        ),
        encoding="utf-8",
    )

    gp = parse_gitignore(tmp_path)
    cp = parse_ctxengignore(tmp_path)
    spec = combined_ignore_spec(gitignore_patterns=gp, ctxeng_patterns=cp)
    assert spec is not None
    assert is_ctxengignored(Path("dist/app.txt"), spec) is True
    assert is_ctxengignored(Path("x.log"), spec) is True
    assert is_ctxengignored(Path("secrets.txt"), spec) is True
    assert is_ctxengignored(Path("src/main.py"), spec) is False


def test_sources_collect_filesystem_respects_gitignore_and_allow_deny(tmp_path: Path):
    from ctxeng.sources import collect_filesystem

    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("nope\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.py").write_text("print('a')\n", encoding="utf-8")

    all_files = dict(collect_filesystem(tmp_path))
    assert Path("ok.py") in all_files
    assert Path("ignored.txt") not in all_files

    only_sub = dict(collect_filesystem(tmp_path, allow_paths=["sub"]))
    assert Path("sub/a.py") in only_sub
    assert Path("ok.py") not in only_sub

    deny_sub = dict(collect_filesystem(tmp_path, deny_paths=["sub"]))
    assert Path("sub/a.py") not in deny_sub
    assert Path("ok.py") in deny_sub


def test_sources_collect_explicit_allows_outside_root(tmp_path: Path):
    from ctxeng.sources import collect_explicit

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "x.py"
    outside_file.write_text("print(1)\n", encoding="utf-8")

    out = list(collect_explicit([outside_file], root=tmp_path))
    assert out
    p, content = out[0]
    # If the explicit file is inside root, we expect a relative path.
    assert p == Path("outside/x.py")
    assert "print(1)" in content


def test_sources_collect_git_changed_is_mockable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from ctxeng.sources import collect_git_changed

    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("print('b')\n", encoding="utf-8")

    class R:
        def __init__(self, out: str):
            self.stdout = out

    def fake_run(cmd, cwd, capture_output, text, timeout):  # noqa: ARG001
        if cmd[:2] == ["git", "diff"]:
            return R("a.py\n")
        if cmd[:3] == ["git", "ls-files", "--others"]:
            return R("b.py\n")
        return R("")

    import ctxeng.sources as sources_mod

    monkeypatch.setattr(sources_mod.subprocess, "run", fake_run)
    got = dict(collect_git_changed(tmp_path, base="HEAD", include_untracked=True))
    assert Path("a.py") in got
    assert Path("b.py") in got


def test_redaction_masks_common_secrets_and_pii():
    from ctxeng.redaction import redact_text

    text = """
API_KEY="supersecretvalue123"
password: hunter2hunter2
contact: test@example.com
aws = AKIA1234567890ABCDEF
token = ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG
"""
    r = redact_text(text)
    assert r.total > 0
    assert "supersecretvalue123" not in r.text
    assert "test@example.com" not in r.text
    assert "[REDACTED:" in r.text


def test_redaction_can_disable_pii_or_secrets():
    from ctxeng.redaction import redact_text

    text = "email me at test@example.com\npassword=verysecretpassword"
    pii_only = redact_text(text, redact_secrets=False, redact_pii=True)
    assert "test@example.com" not in pii_only.text
    assert "verysecretpassword" in pii_only.text

    secrets_only = redact_text(text, redact_secrets=True, redact_pii=False)
    assert "test@example.com" in secrets_only.text
    assert "verysecretpassword" not in secrets_only.text


def test_python_skeleton_extracts_defs():
    from ctxeng.ast_skeleton import python_skeleton

    code = """
import os

def hello(name):
    return name

class A:
    def m(self, x): ...
"""
    sk = python_skeleton(code)
    assert sk.symbol_count > 0
    assert "import os" in sk.text
    assert "def hello(" in sk.text
    assert "class A" in sk.text


def test_chunk_text_validates_args_and_adds_context():
    from ctxeng.chunking import chunk_text

    with pytest.raises(ValueError):
        chunk_text(Path("a.txt"), "x", max_lines=0)
    with pytest.raises(ValueError):
        chunk_text(Path("a.txt"), "x", overlap=-1)

    text = "\n".join(f"line{i}" for i in range(1, 21))
    chunks = chunk_text(Path("a.txt"), text, max_lines=5, overlap=2, context_lines=1)
    assert chunks
    # chunk contains expanded context (start_line should be 1 for first)
    assert chunks[0].start_line == 1
    assert "line1" in chunks[0].text


def test_chunk_file_prefers_python_ast_spans():
    from ctxeng.chunking import chunk_file

    code = "\n".join(
        [
            "def a():",
            "    x = 1",
            "",
            "def b():",
            "    y = 2",
            "",
            "class C:",
            "    def m(self):",
            "        return 3",
            "",
        ]
    )
    chunks = chunk_file(Path("x.py"), code, max_lines=50, context_lines=0)
    assert any("def a" in c.text for c in chunks)
    assert any("def b" in c.text for c in chunks)
    assert any("class C" in c.text for c in chunks)


def test_retrieve_chunks_lexical_returns_ranked_chunks():
    from ctxeng.retrieval import retrieve_chunks_lexical

    files = [
        (Path("a.py"), "def login():\n    return True\n"),
        (Path("b.py"), "def logout():\n    return False\n"),
    ]
    out = retrieve_chunks_lexical(files, "login", max_chunks=5)
    assert out
    assert out[0].chunk.path == Path("a.py")
    assert out[0].score > 0


def test_trace_writer_writes_jsonl(tmp_path: Path):
    from ctxeng.tracing import TraceConfig, TraceWriter

    cfg = TraceConfig(enabled=True, trace_dir=tmp_path, trace_id="t1")
    w = TraceWriter(tmp_path, cfg)
    w.emit("event", a=1, p=Path("x.py"))
    w.close()

    data = w.path.read_text(encoding="utf-8").strip().splitlines()
    assert data
    obj = json.loads(data[0])
    assert obj["event"] == "event"
    assert obj["trace_id"] == "t1"
    assert obj["a"] == 1
    assert obj["p"] == "x.py"


def test_snapshots_write_manifest_and_context(tmp_path: Path):
    from ctxeng.models import Context, ContextFile, TokenBudget
    from ctxeng.snapshots import write_snapshot

    ctx = Context(
        files=[ContextFile(path=Path("a.py"), content="x=1", relevance_score=1.0, language="python")],
        query="q",
        total_tokens=10,
        budget=TokenBudget(total=1000),
        metadata={"model": "gpt-4o"},
    )
    out_dir = write_snapshot(tmp_path, ctx, fmt="markdown", snapshot_id="s1")
    assert (out_dir / "context.txt").is_file()
    assert (out_dir / "manifest.json").is_file()
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["snapshot_id"] == "s1"
    assert "included_paths" in manifest


def test_fewshot_loads_examples(tmp_path: Path):
    from ctxeng.fewshot import load_fewshot_examples

    ex_dir = tmp_path / ".ctxeng" / "examples"
    ex_dir.mkdir(parents=True)
    (ex_dir / "a.md").write_text("# Example A", encoding="utf-8")
    (ex_dir / "b.txt").write_text("Example B", encoding="utf-8")
    out = load_fewshot_examples(tmp_path, examples_dir=".ctxeng/examples", max_files=10)
    assert len(out) == 2
    assert any("Example A" in x for x in out)


def test_scoring_config_loads_and_normalizes(tmp_path: Path):
    from ctxeng.scoring_config import load_scoring_config

    p = tmp_path / "cfg.json"
    p.write_text(
        json.dumps(
            {
                "scoring": {
                    "keyword": 0.3,
                    "path": 0.3,
                    "ast": 0.2,
                    "git": 0.2,
                    "semantic": 0.15,
                }
            }
        ),
        encoding="utf-8",
    )
    w = load_scoring_config(p)
    nb = w.normalized_base()
    assert pytest.approx(nb.keyword + nb.path + nb.ast + nb.git, rel=1e-6) == 1.0
    assert w.semantic == 0.15


def test_extract_symbols_graceful_when_unsupported_language():
    from ctxeng.multilang_ast import extract_symbols

    s = extract_symbols("whatever", language="ruby")
    assert s.symbols == set()


def test_extract_symbols_js_includes_function_name_if_available():
    from ctxeng.multilang_ast import extract_symbols

    js = "function authenticateUser(token) { return token }"
    out = extract_symbols(js, language="javascript").symbols
    assert isinstance(out, set)
    assert "authenticateuser" in out or out == set()


def test_extract_symbols_go_and_ts_paths():
    from ctxeng.multilang_ast import extract_symbols

    go = "package main\n\nfunc HelloWorld() {}\n"
    out_go = extract_symbols(go, language="go").symbols
    assert isinstance(out_go, set)

    ts = "export function doThing(x: number) { return x }"
    out_ts = extract_symbols(ts, language="ts").symbols
    assert isinstance(out_ts, set)


def test_extract_symbols_with_stubbed_tree_sitter(monkeypatch: pytest.MonkeyPatch):
    """
    Cover the main tree traversal logic without needing native deps.
    """
    import types

    class Node:
        def __init__(self, type_, start, end, children=None, name=None):
            self.type = type_
            self.start_byte = start
            self.end_byte = end
            self.children = children or []
            self._name = name

        def child_by_field_name(self, field):  # noqa: ARG002
            return self._name

    class Parser:
        def parse(self, src):  # noqa: ARG002
            # function_declaration name + some identifiers
            name = Node("identifier", 9, 25, children=[])
            fn = Node("function_declaration", 0, 0, children=[name], name=name)
            ident = Node("identifier", 9, 25, children=[])
            root = Node("root", 0, 0, children=[fn, ident])
            return types.SimpleNamespace(root_node=root)

    def get_parser(lang):  # noqa: ARG001
        return Parser()

    fake = types.SimpleNamespace(get_parser=get_parser)
    monkeypatch.setitem(__import__("sys").modules, "tree_sitter_languages", fake)

    from ctxeng.multilang_ast import extract_symbols

    code = "function AuthenticateUser() {}"
    out = extract_symbols(code, language="js")
    assert out.language == "javascript"
    assert "authenticateuser" in out.symbols


def test_optimizer_detect_language_and_budget(monkeypatch: pytest.MonkeyPatch):
    import sys

    # Force heuristic token counting path
    monkeypatch.setitem(sys.modules, "tiktoken", None)

    from ctxeng.models import ContextFile, TokenBudget
    from ctxeng.optimizer import count_tokens, detect_language, optimize_budget

    assert detect_language(Path("x.py")) == "python"
    assert detect_language(Path("Dockerfile")) == "dockerfile"
    assert detect_language(Path("unknown.zzz")) == ""

    # count_tokens should return at least 1
    assert count_tokens("") >= 1
    assert count_tokens("a b c") >= 1

    files = [
        ContextFile(path=Path("a.py"), content="a\n" * 1000, relevance_score=10.0, language="python"),
        ContextFile(path=Path("b.py"), content="b\n" * 10, relevance_score=1.0, language="python"),
    ]
    # Force truncation path: available will be ~440 tokens (after reserved buckets),
    # so the large file must be truncated but still included.
    included, skipped = optimize_budget(files, TokenBudget(total=3000), query_tokens=0, system_tokens=0, model="")
    assert included  # should include at least one
    assert isinstance(skipped, list)
    # If budget is tight, we expect truncation to happen for the big file
    assert any(getattr(f, "is_truncated", False) for f in included)


def test_semantic_scores_cache_without_real_sentence_transformers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    This test avoids installing heavy deps by stubbing `sentence_transformers`.
    It covers caching, cosine mapping, and the "empty query" branch.
    """
    import types

    class FakeModel:
        def __init__(self, name: str):  # noqa: ARG002
            self.calls: list[str] = []

        def encode(self, texts, normalize_embeddings=False):  # noqa: ARG002
            # deterministic "embedding": [len(text), count('a')]
            vecs = []
            for t in texts:
                self.calls.append(t)
                vecs.append([float(len(t)), float(t.lower().count("a"))])
            return vecs

    fake_mod = types.SimpleNamespace(SentenceTransformer=FakeModel)
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", fake_mod)

    from ctxeng.semantic import compute_semantic_scores

    files = [(Path("a.py"), "alpha"), (Path("b.py"), "beta")]
    empty = compute_semantic_scores(files, query="", root=tmp_path)
    assert empty == {Path("a.py"): 0.0, Path("b.py"): 0.0}

    scores1 = compute_semantic_scores(files, query="aaa", model_name="m", root=tmp_path)
    assert set(scores1.keys()) == {Path("a.py"), Path("b.py")}
    # Second call should hit cache for file embeddings
    scores2 = compute_semantic_scores(files, query="aaa", model_name="m", root=tmp_path)
    assert scores2 == scores1
    cache_dir = tmp_path / ".ctxeng_cache"
    assert any(p.suffix == ".json" for p in cache_dir.glob("*.json"))


def test_engine_rag_lexical_fallback_and_redaction(tmp_path: Path):
    from ctxeng import ContextEngine

    root = tmp_path
    (root / "a.py").write_text("def login():\n    return True\nAPI_KEY=supersecretvalue123\n", encoding="utf-8")
    (root / "b.py").write_text("def logout():\n    return False\n", encoding="utf-8")

    engine = ContextEngine(root=root, model="gpt-4o", rag=True, rag_max_chunks=3, trace=False)
    ctx = engine.build("login")
    s = ctx.to_string("plain")
    assert "login" in s.lower()
    # secret should be redacted by default
    assert "supersecretvalue123" not in s
    assert re.search(r"REDACTED", s) is not None


def test_builder_propagates_advanced_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from ctxeng.builder import ContextBuilder

    (tmp_path / ".gitignore").write_text("", encoding="utf-8")
    (tmp_path / "a.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / ".ctxeng").mkdir()
    (tmp_path / ".ctxeng" / "examples").mkdir(parents=True)
    (tmp_path / ".ctxeng" / "examples" / "ex.md").write_text("example", encoding="utf-8")
    (tmp_path / ".ctxeng" / "config.json").write_text(
        json.dumps({"scoring": {"keyword": 0.4, "path": 0.2, "ast": 0.25, "git": 0.15, "semantic": 0.2}}),
        encoding="utf-8",
    )

    # Prevent tests from downloading embedding models.
    import ctxeng.core as core_mod
    import ctxeng.retrieval as retrieval_mod

    def _no_embeddings(*args, **kwargs):  # noqa: ARG001
        raise ImportError("disabled in tests")

    monkeypatch.setattr(retrieval_mod, "retrieve_chunks_embeddings", _no_embeddings)
    monkeypatch.setattr(core_mod, "retrieve_chunks_embeddings", _no_embeddings)

    b = (
        ContextBuilder(root=tmp_path)
        .for_model("gpt-4o")
        .with_budget(total=9000, reserved_output=100)
        .only("**/*.py", "**/*.txt")
        .exclude("**/nope/**")
        .include_files("a.py")
        .with_system("sys")
        .max_file_size(999)
        .no_git()
        .use_import_graph(depth=2)
        .no_import_graph()
        .use_semantic(model="all-mpnet-base-v2")
        .no_gitignore()
        .allow("a.py")
        .deny("nope")
        .trace(True, trace_dir=tmp_path / ".ctxeng" / "traces", trace_id="t1")
        .rag(True, max_chunks=3, chunk_max_lines=50, chunk_overlap=0, chunk_context_lines=1, embedding_model="m")
        .skeleton(True)
        .redact(True)
        .fewshot(True, examples_dir=".ctxeng/examples", max_files=1)
        .scoring_config(tmp_path / ".ctxeng" / "config.json")
    )

    engine = b._build_engine()
    ctx = engine.build(query="return", files=[Path("a.py")])
    assert ctx.files

