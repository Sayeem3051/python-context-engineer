"""
Drop-in integrations for popular LLM clients.

These helpers take a Context object and call the LLM directly,
so you never have to manually paste context again.

Example (Claude)::

    from ctxeng import ContextEngine
    from ctxeng.integrations import ask_claude

    engine = ContextEngine(".", model="claude-sonnet-4")
    ctx = engine.build("Why is the login test failing?")
    response = ask_claude(ctx)
    print(response)

Example (OpenAI)::

    from ctxeng import ContextEngine
    from ctxeng.integrations import ask_openai

    engine = ContextEngine(".", model="gpt-4o")
    ctx = engine.build("Refactor this to be async")
    response = ask_openai(ctx)
    print(response)
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ctxeng.models import Context


def ask_claude(
    ctx: "Context",
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    fmt: str = "xml",
) -> str:
    """
    Send a Context to Anthropic's Claude API and return the response text.

    Requires: ``pip install anthropic``

    Args:
        ctx:        The context built by ContextEngine or ContextBuilder.
        api_key:    Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
        model:      Model to use. Defaults to claude-sonnet-4-20250514.
        max_tokens: Max response tokens (default 4096).
        fmt:        Context rendering format ('xml' recommended for Claude).

    Returns:
        The assistant's response as a string.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic package required: pip install anthropic"
        ) from None

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    model = model or "claude-sonnet-4-20250514"

    messages = [{"role": "user", "content": ctx.to_string(fmt)}]

    kwargs: dict = dict(model=model, max_tokens=max_tokens, messages=messages)
    if ctx.system_prompt:
        kwargs["system"] = ctx.system_prompt

    response = client.messages.create(**kwargs)
    return response.content[0].text


def ask_openai(
    ctx: "Context",
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    fmt: str = "markdown",
) -> str:
    """
    Send a Context to the OpenAI API and return the response text.

    Requires: ``pip install openai``

    Args:
        ctx:        The context built by ContextEngine or ContextBuilder.
        api_key:    OpenAI API key. Falls back to OPENAI_API_KEY env var.
        model:      Model to use. Defaults to gpt-4o.
        max_tokens: Max response tokens (default 4096).
        fmt:        Context rendering format ('markdown' recommended for OpenAI).

    Returns:
        The assistant's response as a string.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package required: pip install openai"
        ) from None

    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    model = model or "gpt-4o"

    messages = []
    if ctx.system_prompt:
        messages.append({"role": "system", "content": ctx.system_prompt})
    messages.append({"role": "user", "content": ctx.to_string(fmt)})

    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    return response.choices[0].message.content or ""


def to_langchain_messages(ctx: "Context", fmt: str = "xml") -> list:
    """
    Convert a Context to a list of LangChain message objects.

    Requires: ``pip install langchain-core``

    Returns:
        List of [SystemMessage?, HumanMessage] suitable for any LangChain chat model.
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
    except ImportError:
        raise ImportError(
            "langchain-core required: pip install langchain-core"
        ) from None

    messages = []
    if ctx.system_prompt:
        messages.append(SystemMessage(content=ctx.system_prompt))
    messages.append(HumanMessage(content=ctx.to_string(fmt)))
    return messages
