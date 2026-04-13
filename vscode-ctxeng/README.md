# CtxEng AI - Intelligent Context Engineering for VSCode

> **Note:** The VSCode extension is **disabled in this version** because it is still **under development**.\n+> Please use the `ctxeng` CLI / Python package instead for now.
<p align="center">
  <img src="https://raw.githubusercontent.com/Sayeem3051/python-context-engineer/main/vscode-ctxeng/media/ctxeng.png" alt="CtxEng AI Logo" width="128" height="128">
</p>

<p align="center">
  <strong>Stop copy-pasting files into ChatGPT.<br>
  Build perfect LLM context from your codebase, automatically.</strong>
</p>

<p align="center">
  <a href="https://marketplace.visualstudio.com/items?itemName=saeemabkari6.ctxeng-ai">
    <img src="https://img.shields.io/visual-studio-marketplace/v/saeemabkari6.ctxeng-ai?color=blue&label=VS%20Code%20Marketplace" alt="VS Code Marketplace">
  </a>
  <a href="https://marketplace.visualstudio.com/items?itemName=saeemabkari6.ctxeng-ai">
    <img src="https://img.shields.io/visual-studio-marketplace/d/saeemabkari6.ctxeng-ai?color=green" alt="Downloads">
  </a>
  <a href="https://marketplace.visualstudio.com/items?itemName=saeemabkari6.ctxeng-ai">
    <img src="https://img.shields.io/visual-studio-marketplace/r/saeemabkari6.ctxeng-ai?color=yellow" alt="Rating">
  </a>
</p>

Transform your development workflow with AI-powered context engineering. CtxEng AI automatically analyzes your codebase, selects the most relevant files for your query, and provides intelligent responses from 11+ AI providers including Claude, GPT-4o, Gemini, and more.

## ✨ Features at a Glance

- 🧠 **Smart Context Building** - Automatically scores and ranks files by relevance
- 🤖 **11+ AI Providers** - OpenAI, Anthropic, Google, Mistral, Groq, and more
- 🔒 **Secure API Keys** - Encrypted storage in VSCode SecretStorage
- ⚡ **Real-time Streaming** - Live AI responses with token-by-token updates
- 📊 **Cost Estimation** - Track token usage and estimated costs
- 🔍 **Diff Viewer** - Compare AI suggestions with your code
- 📁 **Smart File Selection** - Click to open files directly in editor
- ⚙️ **Flexible Configuration** - Customize models, formats, and behavior

## 📸 Screenshots

### Main Sidebar Interface
![CtxEng AI Sidebar](images/sidebar.png)

### AI Chat Interface
![AI Chat Interface](images/ask-ai.png)

## 🚀 Quick Start

### Prerequisites
1. **Install Python Package**
   ```bash
   pip install ctxeng
   ```

2. **Install Extension**
   - Open VSCode
   - Go to Extensions (Ctrl+Shift+X)
   - Search for "CtxEng AI"
   - Click Install

3. **Verify Installation**
   - Press `Ctrl+Shift+P`
   - Run `CtxEng: Verify Installation`
   - If successful, proceed to setup API key

4. **Setup API Key**
   - Open Command Palette (Ctrl+Shift+P)
   - Run `CtxEng: Set API Key`
   - Choose your preferred AI provider
   - Enter your API key (stored securely)

### First Use
1. Open any project folder in VSCode
2. Click the CtxEng AI icon in the Activity Bar
3. Enter your query (e.g., "Explain the authentication flow")
4. Watch as CtxEng builds context and provides AI insights!

### 🔧 Troubleshooting
If you encounter issues, see our [Setup Guide](SETUP_GUIDE.md) for detailed troubleshooting steps.

**Common Issues:**
- **"ctxeng CLI not found"**: Run the diagnostic script or check PATH configuration
- **Permission errors**: Try `pip install --user ctxeng`
- **Network issues**: Check internet connection and API key validity

**Quick Fixes:**
```bash
# Windows: Add to PATH
%APPDATA%\Python\Python314\Scripts

# macOS/Linux: Add to PATH  
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
ctxeng info
```

## 🎯 Core Features

### Intelligent Context Building
CtxEng uses advanced scoring algorithms to automatically select the most relevant files:
- **Keyword Matching** - Finds files containing query-related terms
- **AST Analysis** - Analyzes code structure and symbols (Python)
- **Path Relevance** - Considers file naming and location
- **Git Recency** - Prioritizes recently modified files
- **Import Graph** - Includes related dependencies
- **Semantic Similarity** - Optional embedding-based matching

### Multi-Provider AI Support
Choose from 11+ leading AI providers:

| Provider | Models | Strengths |
|----------|--------|-----------|
| **OpenAI** | GPT-4o, GPT-4-turbo, GPT-3.5-turbo | General purpose, coding |
| **Anthropic** | Claude Opus/Sonnet/Haiku 4 | Reasoning, analysis |
| **Google** | Gemini 1.5 Pro/Flash, 2.0 Flash | Multimodal, large context |
| **Mistral** | Large/Medium/Small, Codestral | European, coding-focused |
| **Groq** | Llama 3.3, Mixtral, Gemma2 | Ultra-fast inference |
| **Cohere** | Command R+/R/Light | Enterprise, RAG |
| **Together** | Llama 3, Mixtral, Qwen | Open source models |
| **DeepSeek** | DeepSeek Chat/Reasoner | Reasoning, math |
| **xAI** | Grok 2/2-mini | Real-time, conversational |
| **OpenRouter** | 100+ models | Model aggregator |
| **Ollama** | Local models | Privacy, offline |

### Advanced Workflow Features

#### 🔄 **Real-time Streaming**
- Token-by-token response streaming
- Live progress indicators
- Graceful fallback for non-streaming providers

#### 📊 **Smart Metrics Dashboard**
- Live token count tracking
- Cost estimation per query
- File inclusion statistics
- Budget optimization insights

#### 🔍 **Interactive Diff Viewer**
- Compare AI suggestions with original code
- Side-by-side diff visualization
- One-click code application

#### 📁 **Seamless File Navigation**
- Click any file in context to open in editor
- Automatic Explorer reveal
- Smart file filtering and selection

## ⌨️ Commands & Shortcuts

| Command | Shortcut | Description |
|---------|----------|-------------|
| `CtxEng: Build Context for Query` | `Ctrl+Shift+C` | Build context for custom query |
| `CtxEng: Build Context for Current File` | - | Focus context on active file |
| `CtxEng: Watch and Auto-rebuild Context` | - | Auto-rebuild on file changes |
| `CtxEng: Show Context Summary` | - | Display context statistics |
| `CtxEng: Set API Key` | - | Configure provider API key |
| `CtxEng: Clear API Key` | - | Remove stored API key |
| `CtxEng: List Configured Providers` | - | Show available providers |

## ⚙️ Configuration

Customize CtxEng AI behavior through VSCode settings:

### AI Provider Settings
```json
{
  "ctxeng.aiProvider": "openai",           // Default AI provider
  "ctxeng.aiModel": "gpt-4o-mini",         // Default model
  "ctxeng.model": "claude-sonnet-4",       // CtxEng context model
  "ctxeng.format": "markdown"              // Output format (xml/markdown/plain)
}
```

### Provider-Specific Settings
```json
{
  // Ollama (Local)
  "ctxeng.ollamaBaseUrl": "http://localhost:11434",
  "ctxeng.ollamaModels": ["llama3", "mistral", "codellama", "phi3"],
  
  // OpenRouter
  "ctxeng.openrouterModel": "anthropic/claude-3.5-sonnet",
  "ctxeng.openrouterSiteName": "CtxEng VS Code",
  
  // Auto-watch
  "ctxeng.autowatch": false               // Auto-rebuild on file changes
}
```

## 🔧 Advanced Usage

### Custom Context Patterns
Use `.ctxengignore` files to control which files are included:
```gitignore
# Exclude test files
tests/
**/*test*.py

# Exclude build artifacts
dist/
build/
node_modules/

# Include specific patterns
!important-config.json
```

### Semantic Similarity (Optional)
Enable semantic scoring for better relevance:
```bash
pip install "ctxeng[semantic]"
```

### Watch Mode
Auto-rebuild context when files change:
```bash
pip install "ctxeng[watch]"
```

## 🛠️ Troubleshooting

### Common Issues

**❌ "ctxeng not installed"**
```bash
pip install ctxeng
# Restart VSCode after installation
```

**❌ "No API key configured"**
- Run `CtxEng: Set API Key` command
- Ensure you have a valid API key for your chosen provider

**❌ "Network error"**
- Check internet connection
- Verify API key is valid and has sufficient credits
- For Ollama: ensure local server is running

**❌ "Model not found"**
- Check if model name is correct in settings
- Verify your API key has access to the specified model

### Performance Tips
- Use `.ctxengignore` to exclude large/irrelevant files
- Choose appropriate models based on context size
- Enable semantic scoring only for complex queries

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](https://github.com/Sayeem3051/python-context-engineer/blob/main/CONTRIBUTING.md) for details.

### Development Setup
```bash
git clone https://github.com/Sayeem3051/python-context-engineer.git
cd python-context-engineer/vscode-ctxeng
npm install
npm run compile
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🔗 Links

- **GitHub Repository**: [python-context-engineer](https://github.com/Sayeem3051/python-context-engineer)
- **Python Package**: [ctxeng on PyPI](https://pypi.org/project/ctxeng/)
- **Issues & Support**: [GitHub Issues](https://github.com/Sayeem3051/python-context-engineer/issues)
- **Documentation**: [Full Documentation](https://github.com/Sayeem3051/python-context-engineer#readme)

---

<p align="center">
  <strong>Transform your coding workflow with intelligent context engineering!</strong><br>
  Made with ❤️ by <a href="https://github.com/Sayeem3051">Abkari Mohammed Sayeem</a>
</p>
