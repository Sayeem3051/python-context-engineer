"""Redact secrets and PII from context before sending to an LLM."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Redaction:
    kind: str
    label: str
    count: int


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redactions: tuple[Redaction, ...]

    @property
    def total(self) -> int:
        return sum(r.count for r in self.redactions)


def _stable_hash(value: str) -> str:
    h = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()
    return h[:10]


def _sub_all(pattern: re.Pattern[str], text: str, repl_factory) -> tuple[str, int]:
    count = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return repl_factory(m)

    return pattern.sub(_repl, text), count


def redact_text(
    text: str,
    *,
    redact_secrets: bool = True,
    redact_pii: bool = True,
) -> RedactionResult:
    """
    Redact common secrets and PII patterns.

    Design goals:
    - High-confidence redactions by default (avoid breaking code too much).
    - Deterministic placeholders with stable hashes to support debugging
      without revealing original values.
    """
    redactions: list[Redaction] = []
    out = text

    if redact_secrets:
        rules: list[tuple[str, str, re.Pattern[str]]] = [
            # Private keys / certs
            ("secret", "private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----")),
            ("secret", "ssh_private_key", re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----[\s\S]+?-----END OPENSSH PRIVATE KEY-----")),
            # Cloud/API key-ish patterns (high confidence)
            ("secret", "aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
            ("secret", "github_token", re.compile(r"\bgh[pous]_[A-Za-z0-9]{36,}\b")),
            ("secret", "slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
            # Generic assignments: key=..., token: ...
            ("secret", "api_key_assignment", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*([\"']?)([^\"'\n\r]{8,})\2")),
        ]

        for kind, label, pat in rules:
            if label == "api_key_assignment":
                def repl(m: re.Match[str]) -> str:
                    key = m.group(1)
                    quote = m.group(2) or ""
                    val = m.group(3)
                    return f"{key}: {quote}[REDACTED:{label}:{_stable_hash(val)}]{quote}"

                out, c = _sub_all(pat, out, repl)
            else:
                out, c = _sub_all(
                    pat,
                    out,
                    lambda m, _label=label: f"[REDACTED:{_label}:{_stable_hash(m.group(0))}]",
                )
            if c:
                redactions.append(Redaction(kind=kind, label=label, count=c))

    if redact_pii:
        pii_rules: Iterable[tuple[str, re.Pattern[str]]] = [
            ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
            ("phone", re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}\b")),
            ("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
        ]
        for label, pat in pii_rules:
            out, c = _sub_all(pat, out, lambda m, _label=label: f"[REDACTED:{_label}:{_stable_hash(m.group(0))}]")
            if c:
                redactions.append(Redaction(kind="pii", label=label, count=c))

    return RedactionResult(text=out, redactions=tuple(redactions))

