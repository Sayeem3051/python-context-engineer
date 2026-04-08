import * as vscode from "vscode";

export interface ProviderConfig {
  id: string;
  displayName: string;
  models: string[];
  requiresApiKey: boolean;
  apiKeyLabel: string;
  apiKeyValidationPrefix?: string;
}

export interface AIProvider {
  config: ProviderConfig;
  call(apiKey: string | null, model: string, systemPrompt: string, userMessage: string, baseUrl?: string): Promise<string>;
  callStream(
    apiKey: string | null,
    model: string,
    systemPrompt: string,
    userMessage: string,
    onChunk: (text: string) => void,
    baseUrl?: string,
  ): Promise<string>;
}

interface ProviderErrorCtx {
  providerName: string;
  model: string;
}

export const PROVIDER_PRIORITY = [
  "anthropic",
  "openai",
  "gemini",
  "mistral",
  "groq",
  "deepseek",
  "xai",
  "cohere",
  "together",
  "openrouter",
  "ollama",
] as const;

const PROVIDERS: Record<string, ProviderConfig> = {
  openai: { id: "openai", displayName: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"], requiresApiKey: true, apiKeyLabel: "OpenAI API key" },
  anthropic: { id: "anthropic", displayName: "Anthropic (Claude)", models: ["claude-opus-4", "claude-sonnet-4", "claude-haiku-4"], requiresApiKey: true, apiKeyLabel: "Anthropic API key" },
  gemini: { id: "gemini", displayName: "Google Gemini", models: ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"], requiresApiKey: true, apiKeyLabel: "Google AI API key" },
  mistral: { id: "mistral", displayName: "Mistral AI", models: ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest", "codestral-latest"], requiresApiKey: true, apiKeyLabel: "Mistral API key" },
  groq: { id: "groq", displayName: "Groq", models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"], requiresApiKey: true, apiKeyLabel: "Groq API key" },
  cohere: { id: "cohere", displayName: "Cohere", models: ["command-r-plus", "command-r", "command-light"], requiresApiKey: true, apiKeyLabel: "Cohere API key" },
  together: { id: "together", displayName: "Together AI", models: ["meta-llama/Llama-3-70b-chat-hf", "mistralai/Mixtral-8x7B-Instruct-v0.1", "Qwen/Qwen2.5-72B-Instruct-Turbo"], requiresApiKey: true, apiKeyLabel: "Together API key" },
  deepseek: { id: "deepseek", displayName: "DeepSeek", models: ["deepseek-chat", "deepseek-reasoner"], requiresApiKey: true, apiKeyLabel: "DeepSeek API key" },
  ollama: { id: "ollama", displayName: "Ollama (Local)", models: [], requiresApiKey: false, apiKeyLabel: "" },
  xai: { id: "xai", displayName: "xAI (Grok)", models: ["grok-2", "grok-2-mini"], requiresApiKey: true, apiKeyLabel: "xAI API key" },
  openrouter: { id: "openrouter", displayName: "OpenRouter", models: [], requiresApiKey: true, apiKeyLabel: "OpenRouter API key" },
};

export function getProviderConfig(providerId: string): ProviderConfig {
  const cfg = PROVIDERS[providerId];
  if (!cfg) throw new Error(`Unknown provider: ${providerId}`);
  return cfg;
}

function bearerHeaders(apiKey: string | null): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
  return headers;
}

function mapHttpError(status: number, ctx: ProviderErrorCtx): string {
  if (status === 401 || status === 403) return `❌ Invalid API key for ${ctx.providerName}. Click 🔑 to update it.`;
  if (status === 429) return `❌ Rate limit hit on ${ctx.providerName}. Wait a moment and retry.`;
  if (status === 404) return `❌ Model "${ctx.model}" not found on ${ctx.providerName}. Check ctxeng.aiModel in settings.`;
  if (status >= 500) return `❌ ${ctx.providerName} server error (HTTP ${status}). Try again shortly.`;
  return `❌ ${ctx.providerName} request failed (HTTP ${status}).`;
}

async function throwIfNotOk(res: Response, ctx: ProviderErrorCtx): Promise<void> {
  if (res.ok) return;
  let suffix = "";
  try { suffix = (await res.text()).trim(); } catch {}
  const msg = mapHttpError(res.status, ctx);
  throw new Error(suffix ? `${msg}\n${suffix}` : msg);
}

function extractOpenAIContent(data: unknown): string {
  const d = data as { choices?: Array<{ message?: { content?: string } }> };
  return d.choices?.[0]?.message?.content?.trim() ?? "";
}

async function streamSse(
  res: Response,
  parseData: (lineData: string) => string,
  onChunk: (text: string) => void,
): Promise<string> {
  if (!res.body) return "";
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buffer = "";
  let out = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += dec.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]" || payload.length === 0) continue;
      const chunk = parseData(payload);
      if (chunk) {
        out += chunk;
        onChunk(chunk);
      }
    }
  }
  return out;
}

class OpenAICompatibleProvider implements AIProvider {
  public constructor(public readonly config: ProviderConfig, private readonly defaultBaseUrl: string) {}

  public async call(apiKey: string | null, model: string, systemPrompt: string, userMessage: string, baseUrl?: string): Promise<string> {
    if (this.config.requiresApiKey && !apiKey) throw new Error(`⚠️ No API key for ${this.config.displayName}. Click 🔑 to add one.`);
    const url = `${(baseUrl ?? this.defaultBaseUrl).replace(/\/$/, "")}/chat/completions`;
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: bearerHeaders(apiKey),
        body: JSON.stringify({
          model,
          messages: [{ role: "system", content: systemPrompt }, { role: "user", content: userMessage }],
          max_tokens: 1200,
          temperature: 0.2,
        }),
      });
    } catch {
      if (this.config.id === "ollama") throw new Error("❌ Ollama not running. Start it with: ollama serve");
      throw new Error(`❌ Cannot reach ${this.config.displayName}. Check your internet connection.`);
    }
    await throwIfNotOk(res, { providerName: this.config.displayName, model });
    const text = extractOpenAIContent((await res.json()) as unknown);
    if (!text) throw new Error(`⚠️ ${this.config.displayName} returned an empty response. Try rephrasing.`);
    return text;
  }

  public async callStream(
    apiKey: string | null,
    model: string,
    systemPrompt: string,
    userMessage: string,
    onChunk: (text: string) => void,
    baseUrl?: string,
  ): Promise<string> {
    if (this.config.requiresApiKey && !apiKey) throw new Error(`⚠️ No API key for ${this.config.displayName}. Click 🔑 to add one.`);
    const url = `${(baseUrl ?? this.defaultBaseUrl).replace(/\/$/, "")}/chat/completions`;
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: bearerHeaders(apiKey),
        body: JSON.stringify({
          model,
          stream: true,
          messages: [{ role: "system", content: systemPrompt }, { role: "user", content: userMessage }],
          max_tokens: 1200,
          temperature: 0.2,
        }),
      });
    } catch {
      if (this.config.id === "ollama") throw new Error("❌ Ollama not running. Start it with: ollama serve");
      throw new Error(`❌ Cannot reach ${this.config.displayName}. Check your internet connection.`);
    }
    await throwIfNotOk(res, { providerName: this.config.displayName, model });
    const text = await streamSse(
      res,
      (payload) => {
        try {
          const obj = JSON.parse(payload) as { choices?: Array<{ delta?: { content?: string } }> };
          return obj.choices?.[0]?.delta?.content ?? "";
        } catch {
          return "";
        }
      },
      onChunk,
    );
    if (!text.trim()) return this.call(apiKey, model, systemPrompt, userMessage, baseUrl);
    return text;
  }
}

class AnthropicProvider implements AIProvider {
  public readonly config = getProviderConfig("anthropic");

  public async call(apiKey: string | null, model: string, systemPrompt: string, userMessage: string): Promise<string> {
    if (!apiKey) throw new Error("⚠️ No API key for Anthropic (Claude). Click 🔑 to add one.");
    const url = "https://api.anthropic.com/v1/messages";
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
        body: JSON.stringify({
          model,
          max_tokens: 1200,
          messages: [{ role: "user", content: userMessage }],
          system: systemPrompt,
        }),
      });
    } catch {
      throw new Error("❌ Cannot reach Anthropic (Claude). Check your internet connection.");
    }
    await throwIfNotOk(res, { providerName: this.config.displayName, model });
    const data = (await res.json()) as { content?: Array<{ type?: string; text?: string }> };
    const text = (data.content ?? []).filter((p) => p.type === "text" && typeof p.text === "string").map((p) => p.text as string).join("\n").trim();
    if (!text) throw new Error("⚠️ Anthropic (Claude) returned an empty response. Try rephrasing.");
    return text;
  }

  public async callStream(
    apiKey: string | null,
    model: string,
    systemPrompt: string,
    userMessage: string,
    onChunk: (text: string) => void,
  ): Promise<string> {
    if (!apiKey) throw new Error("⚠️ No API key for Anthropic (Claude). Click 🔑 to add one.");
    const url = "https://api.anthropic.com/v1/messages";
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
        body: JSON.stringify({
          model,
          max_tokens: 1200,
          stream: true,
          messages: [{ role: "user", content: userMessage }],
          system: systemPrompt,
        }),
      });
    } catch {
      throw new Error("❌ Cannot reach Anthropic (Claude). Check your internet connection.");
    }
    await throwIfNotOk(res, { providerName: this.config.displayName, model });
    const text = await streamSse(
      res,
      (payload) => {
        try {
          const obj = JSON.parse(payload) as { type?: string; delta?: { text?: string } };
          if (obj.type === "content_block_delta") return obj.delta?.text ?? "";
          return "";
        } catch {
          return "";
        }
      },
      onChunk,
    );
    if (!text.trim()) return this.call(apiKey, model, systemPrompt, userMessage);
    return text;
  }
}

class GeminiProvider implements AIProvider {
  public readonly config = getProviderConfig("gemini");

  public async call(apiKey: string | null, model: string, systemPrompt: string, userMessage: string): Promise<string> {
    if (!apiKey) throw new Error("⚠️ No API key for Google Gemini. Click 🔑 to add one.");
    const base = "https://generativelanguage.googleapis.com/v1beta";
    const url = `${base}/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: systemPrompt }] },
          contents: [{ role: "user", parts: [{ text: userMessage }] }],
        }),
      });
    } catch {
      throw new Error("❌ Cannot reach Google Gemini. Check your internet connection.");
    }
    await throwIfNotOk(res, { providerName: this.config.displayName, model });
    const data = (await res.json()) as { candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }> };
    const text = (data.candidates?.[0]?.content?.parts ?? []).map((p) => p.text ?? "").join("\n").trim();
    if (!text) throw new Error("⚠️ Google Gemini returned an empty response. Try rephrasing.");
    return text;
  }

  public async callStream(
    apiKey: string | null,
    model: string,
    systemPrompt: string,
    userMessage: string,
    onChunk: (text: string) => void,
  ): Promise<string> {
    const full = await this.call(apiKey, model, systemPrompt, userMessage);
    onChunk(full);
    return full;
  }
}

class CohereProvider implements AIProvider {
  public readonly config = getProviderConfig("cohere");

  public async call(apiKey: string | null, model: string, systemPrompt: string, userMessage: string): Promise<string> {
    if (!apiKey) throw new Error("⚠️ No API key for Cohere. Click 🔑 to add one.");
    let res: Response;
    try {
      res = await fetch("https://api.cohere.ai/v2/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
        body: JSON.stringify({
          model,
          messages: [{ role: "system", content: systemPrompt }, { role: "user", content: userMessage }],
        }),
      });
    } catch {
      throw new Error("❌ Cannot reach Cohere. Check your internet connection.");
    }
    await throwIfNotOk(res, { providerName: this.config.displayName, model });
    const data = (await res.json()) as { message?: { content?: Array<{ type?: string; text?: string }> } };
    const text = (data.message?.content ?? []).filter((c) => c.type === "text" && typeof c.text === "string").map((c) => c.text as string).join("\n").trim();
    if (!text) throw new Error("⚠️ Cohere returned an empty response. Try rephrasing.");
    return text;
  }

  public async callStream(
    apiKey: string | null,
    model: string,
    systemPrompt: string,
    userMessage: string,
    onChunk: (text: string) => void,
  ): Promise<string> {
    const full = await this.call(apiKey, model, systemPrompt, userMessage);
    onChunk(full);
    return full;
  }
}

class OpenRouterProvider extends OpenAICompatibleProvider {
  public constructor() { super(getProviderConfig("openrouter"), "https://openrouter.ai/api/v1"); }
}

export function getProvider(providerId: string): AIProvider {
  if (providerId === "anthropic") return new AnthropicProvider();
  if (providerId === "gemini") return new GeminiProvider();
  if (providerId === "cohere") return new CohereProvider();
  if (providerId === "openrouter") return new OpenRouterProvider();
  if (providerId === "openai") return new OpenAICompatibleProvider(getProviderConfig("openai"), "https://api.openai.com/v1");
  if (providerId === "mistral") return new OpenAICompatibleProvider(getProviderConfig("mistral"), "https://api.mistral.ai/v1");
  if (providerId === "groq") return new OpenAICompatibleProvider(getProviderConfig("groq"), "https://api.groq.com/openai/v1");
  if (providerId === "together") return new OpenAICompatibleProvider(getProviderConfig("together"), "https://api.together.xyz/v1");
  if (providerId === "deepseek") return new OpenAICompatibleProvider(getProviderConfig("deepseek"), "https://api.deepseek.com/v1");
  if (providerId === "xai") return new OpenAICompatibleProvider(getProviderConfig("xai"), "https://api.x.ai/v1");
  if (providerId === "ollama") {
    const cfg = vscode.workspace.getConfiguration();
    const base = cfg.get<string>("ctxeng.ollamaBaseUrl", "http://localhost:11434");
    return new OpenAICompatibleProvider(getProviderConfig("ollama"), `${base.replace(/\/$/, "")}/v1`);
  }
  throw new Error(`Unsupported provider: ${providerId}`);
}

export function getAllProviderConfigs(): ProviderConfig[] {
  return Object.values(PROVIDERS);
}

export async function isOllamaReachable(baseUrl?: string): Promise<boolean> {
  const cfg = vscode.workspace.getConfiguration();
  const base = (baseUrl ?? cfg.get<string>("ctxeng.ollamaBaseUrl", "http://localhost:11434")).replace(/\/$/, "");
  try {
    const res = await fetch(`${base}/api/tags`, { method: "GET" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function resolveActiveProvider(secrets: vscode.SecretStorage): Promise<string> {
  for (const providerId of PROVIDER_PRIORITY) {
    if (providerId === "ollama") return "ollama";
    const key = await secrets.get(`ctxeng.apiKey.${providerId}`);
    if (key) return providerId;
  }
  return "ollama";
}
