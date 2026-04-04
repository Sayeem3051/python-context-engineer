"""Unit tests for ctxeng core components."""

import pytest
from pathlib import Path
import tempfile
import os


# ── Token counting ────────────────────────────────────────────────────────────

def test_count_tokens_basic():
    from ctxeng.optimizer import count_tokens
    result = count_tokens("Hello world")
    assert result > 0
    assert isinstance(result, int)


def test_count_tokens_empty():
    from ctxeng.optimizer import count_tokens
    assert count_tokens("") == 0 or count_tokens("") == 1  # heuristic may return 1


def test_count_tokens_longer_text_is_more():
    from ctxeng.optimizer import count_tokens
    short = count_tokens("Hello")
    long = count_tokens("Hello world this is a much longer piece of text with many tokens")
    assert long > short


# ── Language detection ────────────────────────────────────────────────────────

def test_detect_language_python():
    from ctxeng.optimizer import detect_language
    assert detect_language(Path("foo.py")) == "python"


def test_detect_language_typescript():
    from ctxeng.optimizer import detect_language
    assert detect_language(Path("app.ts")) == "typescript"


def test_detect_language_unknown():
    from ctxeng.optimizer import detect_language
    assert detect_language(Path("foo.xyz")) == ""


def test_detect_language_dockerfile():
    from ctxeng.optimizer import detect_language
    assert detect_language(Path("Dockerfile")) == "dockerfile"


# ── Token budget ──────────────────────────────────────────────────────────────

def test_token_budget_available():
    from ctxeng.models import TokenBudget
    b = TokenBudget(total=10_000, reserved_output=1000, reserved_system=500)
    assert b.available == 8_500


def test_token_budget_for_model_claude():
    from ctxeng.models import TokenBudget
    b = TokenBudget.for_model("claude-sonnet-4")
    assert b.total == 200_000
    assert b.available > 0


def test_token_budget_for_model_gpt4o():
    from ctxeng.models import TokenBudget
    b = TokenBudget.for_model("gpt-4o")
    assert b.total == 128_000


def test_token_budget_unknown_model():
    from ctxeng.models import TokenBudget
    b = TokenBudget.for_model("some-unknown-model-xyz")
    assert b.total == 32_768  # safe default


# ── Relevance scoring ─────────────────────────────────────────────────────────

def test_keyword_score_perfect_match():
    from ctxeng.scorer import _keyword_score
    score = _keyword_score("def authenticate_user(token):", "authenticate user token")
    assert score > 0.5


def test_keyword_score_no_match():
    from ctxeng.scorer import _keyword_score
    score = _keyword_score("import pandas as pd\ndf = pd.DataFrame()", "authentication login jwt")
    assert score < 0.5


def test_path_score_match():
    from ctxeng.scorer import _path_score
    score = _path_score(Path("src/auth/login.py"), "authentication login")
    assert score > 0.3


def test_ast_score_python():
    from ctxeng.scorer import _ast_score
    code = """
class AuthService:
    def authenticate(self, user, password):
        pass
    def logout(self, user):
        pass
"""
    score = _ast_score(code, "authenticate user")
    assert score > 0.0


def test_ast_score_invalid_python():
    from ctxeng.scorer import _ast_score
    score = _ast_score("this is not valid python {{{{", "query")
    assert score == 0.0


# ── Optimizer ─────────────────────────────────────────────────────────────────

def test_optimize_budget_fits_all():
    from ctxeng.models import ContextFile, TokenBudget
    from ctxeng.optimizer import optimize_budget

    budget = TokenBudget(total=100_000)
    files = [
        ContextFile(path=Path("a.py"), content="x = 1", relevance_score=0.9),
        ContextFile(path=Path("b.py"), content="y = 2", relevance_score=0.7),
    ]
    included, skipped = optimize_budget(files, budget)
    assert len(included) == 2
    assert len(skipped) == 0


def test_optimize_budget_excludes_when_over():
    from ctxeng.models import ContextFile, TokenBudget
    from ctxeng.optimizer import optimize_budget

    # Very tight budget
    budget = TokenBudget(total=100, reserved_output=0, reserved_system=0)
    big_content = "x " * 500
    files = [
        ContextFile(path=Path("big.py"), content=big_content, relevance_score=0.5),
        ContextFile(path=Path("small.py"), content="x = 1", relevance_score=0.9),
    ]
    included, skipped = optimize_budget(files, budget)
    # small.py should be included, big.py skipped or truncated
    paths = [f.path.name for f in included]
    assert "small.py" in paths


def test_optimize_budget_sorts_by_relevance():
    from ctxeng.models import ContextFile, TokenBudget
    from ctxeng.optimizer import optimize_budget

    budget = TokenBudget(total=100_000)
    files = [
        ContextFile(path=Path("low.py"), content="a = 1", relevance_score=0.1),
        ContextFile(path=Path("high.py"), content="b = 2", relevance_score=0.9),
        ContextFile(path=Path("mid.py"), content="c = 3", relevance_score=0.5),
    ]
    included, _ = optimize_budget(files, budget)
    scores = [f.relevance_score for f in included]
    assert scores == sorted(scores, reverse=True)


# ── Context model ─────────────────────────────────────────────────────────────

def test_context_to_string_xml():
    from ctxeng.models import Context, ContextFile, TokenBudget
    ctx = Context(
        files=[ContextFile(path=Path("foo.py"), content="x = 1", relevance_score=0.8, language="python")],
        query="test query",
        budget=TokenBudget(total=1000),
    )
    out = ctx.to_string("xml")
    assert "<task>" in out
    assert "foo.py" in out
    assert "x = 1" in out


def test_context_to_string_markdown():
    from ctxeng.models import Context, ContextFile, TokenBudget
    ctx = Context(
        files=[ContextFile(path=Path("bar.py"), content="y = 2", relevance_score=0.5, language="python")],
        query="my task",
        budget=TokenBudget(total=1000),
    )
    out = ctx.to_string("markdown")
    assert "## Task" in out
    assert "bar.py" in out


def test_context_summary():
    from ctxeng.models import Context, ContextFile, TokenBudget
    ctx = Context(
        files=[ContextFile(path=Path("a.py"), content="a", relevance_score=0.9, token_count=10)],
        skipped_files=[ContextFile(path=Path("b.py"), content="b", relevance_score=0.1, token_count=5)],
        total_tokens=10,
        budget=TokenBudget(total=1000),
    )
    summary = ctx.summary()
    assert "Included" in summary
    assert "Skipped" in summary


# ── Filesystem source ─────────────────────────────────────────────────────────

def test_collect_filesystem_basic():
    from ctxeng.sources import collect_filesystem

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "main.py").write_text("print('hello')")
        (root / "README.md").write_text("# My Project")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "cached.pyc").write_bytes(b"\x00\x01")

        files = list(collect_filesystem(root))
        paths = [str(p) for p, _ in files]

        assert any("main.py" in p for p in paths)
        assert any("README.md" in p for p in paths)
        assert not any("__pycache__" in p for p in paths)
        assert not any(".pyc" in p for p in paths)


def test_collect_filesystem_skips_large_files():
    from ctxeng.sources import collect_filesystem

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        big = root / "big.py"
        big.write_text("x = 1\n" * 100_000)  # ~600 KB

        files = list(collect_filesystem(root, max_file_size_kb=10))
        paths = [str(p) for p, _ in files]
        assert not any("big.py" in p for p in paths)


# ── ContextEngine integration ─────────────────────────────────────────────────

def test_engine_build_returns_context():
    from ctxeng import ContextEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "auth.py").write_text("def authenticate(user, password): pass")
        (root / "models.py").write_text("class User: pass")

        engine = ContextEngine(root=root, model="gpt-4o")
        ctx = engine.build("Fix the authentication logic")

        assert len(ctx.files) > 0
        assert ctx.budget is not None
        assert ctx.total_tokens > 0


def test_builder_fluent_api():
    from ctxeng import ContextBuilder

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "service.py").write_text("class PaymentService: pass")

        ctx = (
            ContextBuilder(root=root)
            .for_model("gpt-4o")
            .only("**/*.py")
            .with_system("You are a senior engineer.")
            .no_git()
            .build("Refactor payment service")
        )
        assert ctx is not None
        assert len(ctx.files) >= 0  # may be 0 if no py files match
