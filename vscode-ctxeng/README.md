# CtxEng AI VSCode Extension

Production-ready VS Code sidebar for building high-quality `ctxeng` context and asking AI providers with secure key storage, live streaming output, and actionable code workflows.

## Installation

1. Install the Python package:
   - `pip install ctxeng`
2. Install this extension (`vscode-ctxeng`) in VSCode.
3. Open a project folder.

## Features

- **CtxEng AI Sidebar**
  - Dedicated "CtxEng AI" activity bar view with provider/model selection, query input, context preview, and AI response panels.
- **Context Build + Explain**
  - `Build Context` runs `ctxeng build --fmt markdown`.
  - `Explain Current File` scopes context to the active file.
- **Live Loading States**
  - Shows `⏳ Building context...` and `⏳ Asking AI...`.
  - Disables actions while tasks are running and restores controls on success/error.
- **Streaming AI Responses**
  - Streams tokens/chunks in real time for providers with streaming APIs.
  - Gracefully falls back to non-streaming providers.
- **Clickable File Navigation**
  - Selected files in the sidebar open directly in editor and are revealed in Explorer.
- **Diff View for AI Suggestions**
  - `Show Diff` compares original selected code (or full file) with AI-generated suggestion using VS Code diff.
- **Metrics Dashboard**
  - Live Tokens / Estimated Cost / Files count from parsed `ctxeng` output.
- **Secure API Keys**
  - Keys are stored in VS Code `SecretStorage` (never in settings).
- **Provider Support**
  - OpenAI, Anthropic, Gemini, Mistral, Groq, Cohere, Together, DeepSeek, Ollama, xAI, OpenRouter.

## Commands

- `ctxeng.buildContext`
- `ctxeng.buildContextCurrentFile`
- `ctxeng.watchContext`
- `ctxeng.showSummary`
- `ctxeng.setApiKey`
- `ctxeng.clearApiKey`
- `ctxeng.listConfiguredProviders`

## Configuration

- `ctxeng.aiProvider` (default: `openai`)
- `ctxeng.aiModel` (default: `gpt-4o-mini`)
- `ctxeng.ollamaBaseUrl` (default: `http://localhost:11434`)
- `ctxeng.ollamaModels` (default: `["llama3","mistral","codellama","phi3"]`)
- `ctxeng.openrouterModel` (default: `anthropic/claude-3.5-sonnet`)
- `ctxeng.openrouterSiteName` (default: `CtxEng VS Code`)
- `ctxeng.model` (default: `claude-sonnet-4`)
- `ctxeng.format` (default: `markdown`)
- `ctxeng.autowatch` (default: `false`)
