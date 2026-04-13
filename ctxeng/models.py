"""Data models for ctxeng."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TokenBudget:
    """Token budget configuration for a target model."""
    total: int
    reserved_output: int = 2048
    reserved_system: int = 512

    @property
    def available(self) -> int:
        return self.total - self.reserved_output - self.reserved_system

    @classmethod
    def for_model(cls, model: str) -> TokenBudget:
        """Return a sensible budget for known models."""
        limits = {
            "claude-opus-4":     200_000,
            "claude-sonnet-4":   200_000,
            "claude-haiku-4":    200_000,
            "gpt-4o":            128_000,
            "gpt-4-turbo":       128_000,
            "gpt-4":              8_192,
            "gpt-3.5-turbo":    16_385,
            "gemini-1.5-pro":  1_000_000,
            "gemini-1.5-flash":1_000_000,
            "llama-3":           32_768,
        }
        for key, limit in limits.items():
            if key in model.lower():
                return cls(total=limit)
        return cls(total=32_768)  # safe default


@dataclass
class ContextFile:
    """A single file included in context, with its relevance metadata."""
    path: Path
    content: str
    relevance_score: float = 0.0
    token_count: int = 0
    inclusion_reason: str = ""
    language: str = ""
    is_truncated: bool = False
    redaction_count: int = 0

    def __repr__(self) -> str:
        status = " [truncated]" if self.is_truncated else ""
        return (
            f"ContextFile(path={self.path.name!r}, "
            f"score={self.relevance_score:.2f}, "
            f"tokens={self.token_count}{status})"
        )


@dataclass
class Context:
    """
    The final assembled context object ready to send to an LLM.

    Attributes:
        files:           Ordered list of included files (highest relevance first).
        system_prompt:   Optional system-level instructions.
        query:           The user's original query or task.
        total_tokens:    Estimated total token count of the full context.
        budget:          The token budget used to build this context.
        skipped_files:   Files that were scored but excluded due to budget.
        metadata:        Extra information (git branch, project name, etc.).
        cost_estimate:   Rough USD cost for input tokens, or ``None`` if unknown model.
    """
    files: list[ContextFile] = field(default_factory=list)
    system_prompt: str = ""
    query: str = ""
    total_tokens: int = 0
    budget: TokenBudget | None = None
    skipped_files: list[ContextFile] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    cost_estimate: float | None = None
    fewshot_examples: list[str] = field(default_factory=list)

    def to_string(self, fmt: str = "xml") -> str:
        """
        Render the context as a formatted string ready to paste into an LLM.

        Args:
            fmt: One of 'xml', 'markdown', 'plain'. Default 'xml' works best
                 with Claude and GPT-4.

        Returns:
            Formatted context string.
        """
        if fmt == "xml":
            return self._render_xml()
        elif fmt == "markdown":
            return self._render_markdown()
        return self._render_plain()

    def _render_xml(self) -> str:
        parts = []
        if self.metadata:
            meta_lines = "\n".join(
                f"  <{k}>{v}</{k}>" for k, v in self.metadata.items()
            )
            parts.append(f"<context_metadata>\n{meta_lines}\n</context_metadata>")

        if self.query:
            parts.append(f"<task>\n{self.query}\n</task>")

        if self.fewshot_examples:
            items = []
            for i, ex in enumerate(self.fewshot_examples, start=1):
                items.append(f"<example index=\"{i}\">\n{ex}\n</example>")
            parts.append("<fewshot_examples>\n" + "\n\n".join(items) + "\n</fewshot_examples>")

        # Index section improves navigation for large contexts.
        if self.files:
            index_lines = []
            for f in self.files:
                flags = []
                if f.is_truncated:
                    flags.append("truncated")
                if getattr(f, "redaction_count", 0):
                    flags.append(f"redactions={getattr(f, 'redaction_count', 0)}")
                index_lines.append(
                    f'  <item path="{f.path}" relevance="{f.relevance_score:.2f}" tokens="{f.token_count}"'
                    + (f' flags="{",".join(flags)}"' if flags else "")
                    + " />"
                )
            parts.append("<context_index>\n" + "\n".join(index_lines) + "\n</context_index>")

        for f in self.files:
            lang = f.language or ""
            truncated = ' truncated="true"' if f.is_truncated else ""
            parts.append(
                f'<file path="{f.path}" relevance="{f.relevance_score:.2f}"{truncated}>\n'
                f"```{lang}\n{f.content}\n```\n</file>"
            )
        return "\n\n".join(parts)

    def _render_markdown(self) -> str:
        parts = []
        if self.query:
            parts.append(f"## Task\n{self.query}")
        if self.metadata:
            meta = "\n".join(f"- **{k}**: {v}" for k, v in self.metadata.items())
            parts.append("## Metadata\n" + meta)

        if self.fewshot_examples:
            ex_parts = []
            for i, ex in enumerate(self.fewshot_examples, start=1):
                ex_parts.append(f"### Example {i}\n{ex}")
            parts.append("## Few-shot examples\n" + "\n\n".join(ex_parts))

        if self.files:
            idx = []
            for f in self.files:
                flags = []
                if f.is_truncated:
                    flags.append("truncated")
                if getattr(f, "redaction_count", 0):
                    flags.append(f"redactions={getattr(f, 'redaction_count', 0)}")
                flag_str = f" ({', '.join(flags)})" if flags else ""
                idx.append(f"- `{f.path}` — score {f.relevance_score:.2f}, ~{f.token_count} tokens{flag_str}")
            parts.append("## Included files\n" + "\n".join(idx))
        for f in self.files:
            lang = f.language or ""
            note = " *(truncated)*" if f.is_truncated else ""
            parts.append(
                f"### `{f.path}`{note}\n```{lang}\n{f.content}\n```"
            )
        return "\n\n".join(parts)

    def _render_plain(self) -> str:
        parts = []
        if self.query:
            parts.append(f"TASK:\n{self.query}")
        for f in self.files:
            parts.append(f"FILE: {f.path}\n{f.content}")
        return "\n\n---\n\n".join(parts)

    def summary(self, *, show_cost: bool = True) -> str:
        """Human-readable summary of what's in the context."""
        avail = self.budget.available if self.budget else 0
        lines = [
            f"Context summary ({self.total_tokens:,} tokens / {avail:,} budget):",
            f"  Included : {len(self.files)} files",
            f"  Skipped  : {len(self.skipped_files)} files (over budget)",
        ]
        if show_cost and self.cost_estimate is not None:
            label = self.metadata.get("pricing_model") or self.metadata.get("model", "model")
            lines.append(f"  Est. cost: ~${self.cost_estimate:.3f} ({label})")
        for f in self.files:
            bar = "█" * int(f.relevance_score * 10)
            lines.append(f"  [{bar:<10}] {f.relevance_score:.2f}  {f.path}")
        return "\n".join(lines)
