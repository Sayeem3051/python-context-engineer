"""Rough API input-token cost estimates (USD per 1K tokens) for planning."""

from __future__ import annotations

# Prices are indicative; check each provider for current rates.
COST_PER_1K_INPUT_TOKENS: dict[str, float] = {
    "claude-opus-4": 0.015,
    "claude-sonnet-4": 0.003,
    "claude-haiku-4": 0.00025,
    "gpt-4o": 0.005,
    "gpt-4-turbo": 0.01,
    "gpt-4": 0.03,
    "gpt-3.5-turbo": 0.0005,
    "gemini-1.5-pro": 0.00125,
    "gemini-1.5-flash": 0.000075,
}


def matched_pricing_model(model: str) -> str | None:
    """
    Return the pricing-table key that matches ``model``, or ``None``.

    Uses the same substring rules as :func:`estimate_cost` (more specific keys
    are listed first in :data:`COST_PER_1K_INPUT_TOKENS`).
    """
    ml = model.lower()
    for key in COST_PER_1K_INPUT_TOKENS:
        if key in ml:
            return key
    return None


def estimate_cost(tokens: int, model: str) -> float | None:
    """
    Estimate USD cost for ``tokens`` input tokens at the given model's rate.

    Args:
        tokens: Estimated input token count.
        model: Model name (matched against :data:`COST_PER_1K_INPUT_TOKENS`).

    Returns:
        Estimated cost in USD, or ``None`` if no pricing entry matches.
    """
    key = matched_pricing_model(model)
    if key is None:
        return None
    rate = COST_PER_1K_INPUT_TOKENS[key]
    return (max(0, tokens) / 1000.0) * rate
