import * as vscode from "vscode";
import * as path from "node:path";

import {
  getAllProviderConfigs,
  getProvider,
  getProviderConfig,
  isOllamaReachable,
  resolveActiveProvider,
} from "./aiClient";
import { buildContext, explainCurrentFile } from "./ctxengRunner";
import {
  CtxengSidebarProvider,
  type BuildPayload,
  type SidebarController,
  type SidebarProviderState,
} from "./sidebarProvider";

const SECRET_PREFIX = "ctxeng.apiKey.";
const WELCOME_DONE_KEY = "ctxeng.welcomeDismissed";

function workspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function cfg(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration();
}

function normalizeCtxengError(error: unknown): string {
  const msg = error instanceof Error ? error.message : String(error);
  if (/not recognized as.*ctxeng|ctxeng not found|is not recognized/i.test(msg)) {
    return "❌ ctxeng not installed. Run: pip install ctxeng";
  }
  if (/No API key/i.test(msg)) return msg;
  if (/Network|ECONNREFUSED|ENOTFOUND/i.test(msg)) return "❌ Network error. Check your connection.";
  return msg;
}

function configuredModelFor(providerId: string): string {
  if (providerId === "openrouter") return cfg().get<string>("ctxeng.openrouterModel", "anthropic/claude-3.5-sonnet");
  if (providerId === "ollama") {
    const models = cfg().get<string[]>("ctxeng.ollamaModels", ["llama3", "mistral", "codellama", "phi3"]);
    return models[0] ?? "llama3";
  }
  return cfg().get<string>("ctxeng.aiModel", "gpt-4o-mini");
}

async function pickProvider(title: string, includeOllama = false): Promise<string | undefined> {
  const providers = getAllProviderConfigs().filter((p) => includeOllama || p.id !== "ollama");
  const pick = await vscode.window.showQuickPick(
    providers.map((p) => ({ label: p.displayName, providerId: p.id })),
    { title, ignoreFocusOut: true },
  );
  return pick?.providerId;
}

async function setApiKey(secrets: vscode.SecretStorage, providerId?: string): Promise<void> {
  const selected = providerId ?? (await pickProvider("Select provider to set API key"));
  if (!selected) return;
  const pc = getProviderConfig(selected);
  const key = await vscode.window.showInputBox({
    title: `Set API Key: ${pc.displayName}`,
    prompt: `Enter ${pc.apiKeyLabel}`,
    password: true,
    ignoreFocusOut: true,
  });
  if (!key?.trim()) return;
  await secrets.store(`${SECRET_PREFIX}${selected}`, key.trim());
  vscode.window.showInformationMessage(`Saved API key for ${pc.displayName}.`);
}

async function clearApiKey(secrets: vscode.SecretStorage, providerId?: string): Promise<void> {
  const selected = providerId ?? (await pickProvider("Select provider to clear API key"));
  if (!selected) return;
  await secrets.delete(`${SECRET_PREFIX}${selected}`);
  vscode.window.showInformationMessage(`Cleared API key for ${getProviderConfig(selected).displayName}.`);
}

async function listConfiguredProviders(secrets: vscode.SecretStorage): Promise<void> {
  const items: vscode.QuickPickItem[] = [];
  for (const p of getAllProviderConfigs().filter((p) => p.id !== "ollama")) {
    const has = Boolean(await secrets.get(`${SECRET_PREFIX}${p.id}`));
    items.push({ label: `${has ? "🟢" : "🔴"} ${p.displayName}`, description: p.id, detail: has ? "Configured" : "Not configured" });
  }
  await vscode.window.showQuickPick(items, { title: "Configured Providers", ignoreFocusOut: true });
}

async function collectState(
  context: vscode.ExtensionContext,
  activeOverride?: { providerId?: string; model?: string },
): Promise<SidebarProviderState> {
  const configuredProviderIds: string[] = [];
  for (const p of getAllProviderConfigs().filter((p) => p.id !== "ollama")) {
    if (await context.secrets.get(`${SECRET_PREFIX}${p.id}`)) configuredProviderIds.push(p.id);
  }

  const ollamaReachable = await isOllamaReachable(cfg().get<string>("ctxeng.ollamaBaseUrl", "http://localhost:11434"));
  let activeProviderId = activeOverride?.providerId ?? cfg().get<string>("ctxeng.aiProvider", "openai");
  if (!activeProviderId || (!configuredProviderIds.includes(activeProviderId) && activeProviderId !== "ollama")) {
    activeProviderId = await resolveActiveProvider(context.secrets);
  }
  const activeModel = activeOverride?.model ?? configuredModelFor(activeProviderId);

  const done = Boolean(await context.globalState.get<boolean>(WELCOME_DONE_KEY));
  const welcomeDismissed = done || configuredProviderIds.length > 0 || ollamaReachable;
  if (welcomeDismissed && !done) await context.globalState.update(WELCOME_DONE_KEY, true);

  return {
    providers: getAllProviderConfigs(),
    configuredProviderIds,
    activeProviderId,
    activeModel,
    openRouterModel: cfg().get<string>("ctxeng.openrouterModel", "anthropic/claude-3.5-sonnet"),
    ollamaReachable,
    ollamaModels: cfg().get<string[]>("ctxeng.ollamaModels", ["llama3", "mistral", "codellama", "phi3"]),
    welcomeDismissed,
  };
}

function extractSuggestion(raw: string): string {
  const m = raw.match(/```[a-zA-Z0-9_-]*\n([\s\S]*?)```/);
  return (m?.[1] ?? raw).trim();
}

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel("ctxeng");
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  status.text = "ctxeng: idle";
  status.show();

  let activeProviderId = cfg().get<string>("ctxeng.aiProvider", "openai");
  let activeModel = cfg().get<string>("ctxeng.aiModel", "gpt-4o-mini");

  const controller: SidebarController = {
    getInitialState: async () => collectState(context, { providerId: activeProviderId, model: activeModel }),
    refreshState: async (next) => {
      if (next?.providerId) activeProviderId = next.providerId;
      if (next?.model) activeModel = next.model;
      return collectState(context, { providerId: activeProviderId, model: activeModel });
    },
    markWelcomeDismissed: async () => {
      await context.globalState.update(WELCOME_DONE_KEY, true);
    },
    setApiKey: async (providerId) => setApiKey(context.secrets, providerId),
    clearApiKey: async (providerId) => clearApiKey(context.secrets, providerId),
    listConfiguredProviders: async () => listConfiguredProviders(context.secrets),
    buildContext: async (query): Promise<BuildPayload> => {
      const root = workspaceRoot();
      if (!root) throw new Error("❌ Open a workspace folder first.");
      status.text = "ctxeng: building...";
      const result = await buildContext({
        cwd: root,
        query,
        model: cfg().get<string>("ctxeng.model", "claude-sonnet-4"),
        format: "markdown",
      });
      if (!result.stdout.trim()) {
        if (result.stderr.trim()) throw new Error(result.stderr.trim());
        throw new Error("⚠️ No relevant files found for this query.");
      }
      status.text = result.summary.tokenCount ? `ctxeng: ${result.summary.tokenCount.toLocaleString()} tok` : "ctxeng: built";
      return { summary: result.summary, contextMarkdown: result.stdout };
    },
    explainCurrentFile: async (query): Promise<BuildPayload> => {
      const root = workspaceRoot();
      const editor = vscode.window.activeTextEditor;
      if (!root || !editor) throw new Error("❌ Open a workspace and file first.");
      status.text = "ctxeng: explaining file...";
      const result = await explainCurrentFile(
        { cwd: root, query, model: cfg().get<string>("ctxeng.model", "claude-sonnet-4"), format: "markdown" },
        editor.document.uri.fsPath,
      );
      if (!result.stdout.trim()) {
        if (result.stderr.trim()) throw new Error(result.stderr.trim());
        throw new Error("⚠️ No relevant files found for this query.");
      }
      status.text = result.summary.tokenCount ? `ctxeng: ${result.summary.tokenCount.toLocaleString()} tok` : "ctxeng: built";
      return { summary: result.summary, contextMarkdown: result.stdout };
    },
    askAI: async ({ providerId, model, query, context: builtContext }, onChunk): Promise<string> => {
      activeProviderId = providerId;
      activeModel = model;
      await cfg().update("ctxeng.aiProvider", providerId, vscode.ConfigurationTarget.Workspace);
      if (providerId === "openrouter") {
        await cfg().update("ctxeng.openrouterModel", model, vscode.ConfigurationTarget.Workspace);
      } else if (providerId !== "ollama") {
        await cfg().update("ctxeng.aiModel", model, vscode.ConfigurationTarget.Workspace);
      }

      const provider = getProvider(providerId);
      const apiKey = provider.config.requiresApiKey ? await context.secrets.get(`${SECRET_PREFIX}${providerId}`) : null;
      if (provider.config.requiresApiKey && !apiKey) {
        throw new Error(`⚠️ No API key for ${provider.config.displayName}. Click 🔑 to add one.`);
      }

      const baseUrl = providerId === "ollama"
        ? `${cfg().get<string>("ctxeng.ollamaBaseUrl", "http://localhost:11434").replace(/\/$/, "")}/v1`
        : providerId === "openrouter"
          ? "https://openrouter.ai/api/v1"
          : undefined;

      const systemPrompt = "You are an expert software engineer. Reply with clear actionable guidance.";
      const userMessage = `Query:\n${query}\n\nContext:\n${builtContext}`;
      output.appendLine(`AI provider: ${provider.config.displayName} / ${model}`);
      return provider.callStream(apiKey ?? null, model, systemPrompt, userMessage, onChunk, baseUrl);
    },
    openFile: async (filePath) => {
      const root = workspaceRoot();
      if (!root) throw new Error("❌ Open a workspace folder first.");
      const uri = vscode.Uri.file(path.resolve(root, filePath));
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc, { preview: false });
      await vscode.commands.executeCommand("revealInExplorer", uri);
    },
    openDiffWithSuggestion: async (suggestedText) => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) throw new Error("❌ Open a file first to show a diff.");
      const suggested = extractSuggestion(suggestedText);
      if (!suggested) throw new Error("⚠️ Empty AI suggestion. Try asking again.");

      const selection = editor.selection;
      const original = selection && !selection.isEmpty ? editor.document.getText(selection) : editor.document.getText();
      const language = editor.document.languageId;
      const leftDoc = await vscode.workspace.openTextDocument({ content: original, language });
      const rightDoc = await vscode.workspace.openTextDocument({ content: suggested, language });
      await vscode.commands.executeCommand(
        "vscode.diff",
        leftDoc.uri,
        rightDoc.uri,
        "CtxEng AI Suggestion ↔ Original",
      );
    },
  };

  const sidebar = new CtxengSidebarProvider(controller);
  context.subscriptions.push(vscode.window.registerWebviewViewProvider(CtxengSidebarProvider.viewType, sidebar));

  const buildContextCmd = vscode.commands.registerCommand("ctxeng.buildContext", async () => {
    try {
      const query = await vscode.window.showInputBox({ prompt: "Enter query", ignoreFocusOut: true });
      if (!query?.trim()) return;
      const result = await controller.buildContext(query.trim());
      await vscode.env.clipboard.writeText(result.contextMarkdown);
      vscode.window.showInformationMessage("ctxeng context copied to clipboard.");
      await sidebar.postState();
    } catch (error) {
      vscode.window.showErrorMessage(normalizeCtxengError(error));
    }
  });

  const buildCurrentCmd = vscode.commands.registerCommand("ctxeng.buildContextCurrentFile", async () => {
    try {
      const query = await vscode.window.showInputBox({ prompt: "Enter query", ignoreFocusOut: true });
      if (!query?.trim()) return;
      const result = await controller.explainCurrentFile(query.trim());
      await vscode.env.clipboard.writeText(result.contextMarkdown);
      vscode.window.showInformationMessage("ctxeng context for current file copied to clipboard.");
      await sidebar.postState();
    } catch (error) {
      vscode.window.showErrorMessage(normalizeCtxengError(error));
    }
  });

  const watchCmd = vscode.commands.registerCommand("ctxeng.watchContext", async () => {
    const root = workspaceRoot();
    if (!root) {
      vscode.window.showErrorMessage("❌ Open a workspace folder first.");
      return;
    }
    const query = await vscode.window.showInputBox({ prompt: "Enter watch query", ignoreFocusOut: true });
    if (!query?.trim()) return;
    const model = cfg().get<string>("ctxeng.model", "claude-sonnet-4");
    const terminal = vscode.window.createTerminal({ name: "ctxeng watch", cwd: root });
    terminal.show();
    terminal.sendText(`ctxeng watch "${query.replace(/"/g, '\\"')}" --model "${model.replace(/"/g, '\\"')}"`);
  });

  const showSummaryCmd = vscode.commands.registerCommand("ctxeng.showSummary", () => output.show(true));
  const setApiKeyCmd = vscode.commands.registerCommand("ctxeng.setApiKey", async () => {
    await setApiKey(context.secrets);
    await sidebar.postState();
  });
  const clearApiKeyCmd = vscode.commands.registerCommand("ctxeng.clearApiKey", async () => {
    await clearApiKey(context.secrets);
    await sidebar.postState();
  });
  const listProvidersCmd = vscode.commands.registerCommand("ctxeng.listConfiguredProviders", async () => {
    await listConfiguredProviders(context.secrets);
  });

  context.subscriptions.push(output, status, buildContextCmd, buildCurrentCmd, watchCmd, showSummaryCmd, setApiKeyCmd, clearApiKeyCmd, listProvidersCmd);

  const autoWatch = cfg().get<boolean>("ctxeng.autowatch", false);
  if (autoWatch) void vscode.commands.executeCommand("ctxeng.watchContext");
}

export function deactivate(): void {}
