"""
Example: Debug a failing test using ctxeng + Claude.

Run:
    pip install "ctxeng[anthropic]"
    python examples/debug_failing_test.py
"""

import os
from ctxeng import ContextBuilder

# Requires ANTHROPIC_API_KEY in env
try:
    from ctxeng.integrations import ask_claude
    HAS_CLAUDE = True
except ImportError:
    HAS_CLAUDE = False


def main():
    print("Building context for failing test debug session...")

    ctx = (
        ContextBuilder(root=".")          # your project root
        .for_model("claude-sonnet-4")
        .only("**/*.py")                  # Python files only
        .exclude("**/migrations/**")      # skip migrations
        .from_git_diff()                  # only recently changed files
        .with_system(
            "You are a senior Python engineer. "
            "Diagnose the bug concisely. Show the fix as a unified diff."
        )
        .build(
            "The test_authenticate_user test is failing with: "
            "KeyError: 'access_token'. Find the root cause and fix it."
        )
    )

    print(ctx.summary())
    print()

    if HAS_CLAUDE and os.getenv("ANTHROPIC_API_KEY"):
        print("Sending to Claude...\n")
        response = ask_claude(ctx)
        print(response)
    else:
        print("Context ready to paste into your LLM:")
        print("─" * 60)
        print(ctx.to_string())


if __name__ == "__main__":
    main()
