import { randomBytes } from "node:crypto";
import * as vscode from "vscode";

import type { ProviderConfig } from "./aiClient";
import type { ParsedSummary } from "./ctxengRunner";

export interface SidebarProviderState {
  providers: ProviderConfig[];
  configuredProviderIds: string[];
  activeProviderId: string;
  activeModel: string;
  openRouterModel: string;
  ollamaReachable: boolean;
  ollamaModels: string[];
  welcomeDismissed: boolean;
}

export interface BuildPayload {
  summary: ParsedSummary;
  contextMarkdown: string;
}

export interface SidebarController {
  getInitialState(): Promise<SidebarProviderState>;
  setApiKey(providerId: string): Promise<void>;
  clearApiKey(providerId: string): Promise<void>;
  listConfiguredProviders(): Promise<void>;
  refreshState(next?: { providerId?: string; model?: string }): Promise<SidebarProviderState>;
  buildContext(query: string): Promise<BuildPayload>;
  explainCurrentFile(query: string): Promise<BuildPayload>;
  askAI(args: { providerId: string; model: string; query: string; context: string }, onChunk: (chunk: string) => Promise<void>): Promise<string>;
  openFile(path: string): Promise<void>;
  openDiffWithSuggestion(suggestedText: string): Promise<void>;
  markWelcomeDismissed(): Promise<void>;
}

type InboundMessage =
  | { type: "ready" }
  | { type: "buildContext"; query: string }
  | { type: "askAi"; query: string; providerId: string; model: string; context: string }
  | { type: "explainCurrentFile"; query: string }
  | { type: "setApiKey"; providerId: string }
  | { type: "clearApiKey"; providerId: string }
  | { type: "listConfiguredProviders" }
  | { type: "providerChanged"; providerId: string; model: string }
  | { type: "dismissInlineWarning" }
  | { type: "dismissWelcome" }
  | { type: "openOllamaWebsite" }
  | { type: "openFile"; path: string }
  | { type: "openDiff"; suggestedText: string };

export class CtxengSidebarProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "ctxeng.sidebarView";
  private view?: vscode.WebviewView;

  public constructor(private readonly controller: SidebarController) {}

  public resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    const nonce = randomBytes(16).toString("base64");
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this.getHtml(webviewView.webview, nonce);

    webviewView.webview.onDidReceiveMessage(async (message: InboundMessage) => {
      try {
        await this.handle(message);
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        await this.post({ type: "error", message: msg });
        await this.post({ type: "loading", kind: "idle" });
      }
    });
  }

  public async postState(next?: { providerId?: string; model?: string }): Promise<void> {
    await this.post({ type: "state", state: await this.controller.refreshState(next) });
  }

  private async handle(message: InboundMessage): Promise<void> {
    if (message.type === "ready") {
      await this.post({ type: "state", state: await this.controller.getInitialState() });
      return;
    }
    if (message.type === "providerChanged") {
      await this.postState({ providerId: message.providerId, model: message.model });
      return;
    }
    if (message.type === "setApiKey") {
      await this.controller.setApiKey(message.providerId);
      await this.postState();
      return;
    }
    if (message.type === "clearApiKey") {
      await this.controller.clearApiKey(message.providerId);
      await this.postState();
      return;
    }
    if (message.type === "listConfiguredProviders") {
      await this.controller.listConfiguredProviders();
      return;
    }
    if (message.type === "dismissWelcome") {
      await this.controller.markWelcomeDismissed();
      await this.postState();
      return;
    }
    if (message.type === "dismissInlineWarning") {
      await this.post({ type: "inlineWarning", message: "" });
      return;
    }
    if (message.type === "openOllamaWebsite") {
      await vscode.env.openExternal(vscode.Uri.parse("https://ollama.com"));
      return;
    }
    if (message.type === "openFile") {
      await this.controller.openFile(message.path);
      return;
    }
    if (message.type === "openDiff") {
      await this.controller.openDiffWithSuggestion(message.suggestedText);
      return;
    }

    if (message.type === "buildContext") {
      if (!message.query.trim()) {
        await this.post({ type: "error", message: "Please enter a query first." });
        return;
      }
      await this.post({ type: "loading", kind: "build" });
      const result = await this.controller.buildContext(message.query);
      await this.post({ type: "buildResult", payload: result });
      await this.post({ type: "loading", kind: "idle" });
      return;
    }

    if (message.type === "explainCurrentFile") {
      if (!message.query.trim()) {
        await this.post({ type: "error", message: "Please enter a query first." });
        return;
      }
      await this.post({ type: "loading", kind: "build" });
      const result = await this.controller.explainCurrentFile(message.query);
      await this.post({ type: "buildResult", payload: result });
      await this.post({ type: "loading", kind: "idle" });
      return;
    }

    if (message.type === "askAi") {
      if (!message.query.trim()) {
        await this.post({ type: "error", message: "Please enter a query first." });
        return;
      }
      await this.post({ type: "loading", kind: "ask" });
      await this.post({ type: "aiStart" });
      const full = await this.controller.askAI(
        {
          providerId: message.providerId,
          model: message.model,
          query: message.query,
          context: message.context,
        },
        async (chunk: string) => {
          await this.post({ type: "aiChunk", chunk });
        },
      );
      if (!full.trim()) {
        await this.post({ type: "error", message: "⚠️ Provider returned an empty response. Try rephrasing." });
      }
      await this.post({ type: "aiDone" });
      await this.post({ type: "loading", kind: "idle" });
    }
  }

  private async post(message: unknown): Promise<void> {
    if (!this.view) return;
    await this.view.webview.postMessage(message);
  }

  private getHtml(webview: vscode.Webview, nonce: string): string {
    const csp = `default-src 'none'; script-src 'nonce-${nonce}'; style-src ${webview.cspSource} 'unsafe-inline';`;
    return `<!doctype html>
<html>
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="${csp}" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
  body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);background:var(--vscode-editor-background);margin:0;padding:10px}
  .row{display:flex;gap:8px;align-items:center;margin-bottom:8px}
  input,select,button{font:inherit;color:var(--vscode-input-foreground);background:var(--vscode-input-background);border:1px solid var(--vscode-input-border);border-radius:6px;padding:6px 8px}
  button{cursor:pointer}
  button.primary{background:var(--vscode-button-background);color:var(--vscode-button-foreground);border-color:transparent}
  button.primary:hover{background:var(--vscode-button-hoverBackground)}
  button:disabled{opacity:.5;cursor:not-allowed}
  .section{border:1px solid var(--vscode-panel-border);border-radius:8px;padding:8px;margin:8px 0}
  .title{font-size:12px;text-transform:uppercase;opacity:.8;margin-bottom:6px}
  .list{display:flex;flex-direction:column;gap:6px;max-height:130px;overflow:auto}
  .file{display:flex;gap:8px;align-items:center;font-size:12px}
  .file-btn{background:transparent;border:none;color:var(--vscode-textLink-foreground);text-align:left;cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;padding:0}
  .bar{height:8px;background:var(--vscode-progressBar-background);border-radius:999px;min-width:80px;position:relative;overflow:hidden}
  .bar span{position:absolute;left:0;top:0;bottom:0;background:var(--vscode-charts-green)}
  .preview,.response{max-height:220px;overflow:auto;border:1px solid var(--vscode-panel-border);border-radius:8px;padding:8px;white-space:pre-wrap}
  .error{background: color-mix(in srgb, var(--vscode-errorForeground) 12%, transparent);border:1px solid var(--vscode-errorForeground);color:var(--vscode-errorForeground);padding:8px;border-radius:8px;margin:8px 0}
  .warn{background: color-mix(in srgb, var(--vscode-editorWarning-foreground) 14%, transparent);border:1px solid var(--vscode-editorWarning-foreground);color:var(--vscode-editorWarning-foreground);padding:8px;border-radius:8px;margin:8px 0}
  .metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
  .metric{border:1px solid var(--vscode-panel-border);border-radius:8px;padding:6px}
  .metric .k{font-size:11px;opacity:.7}
  .metric .v{font-size:13px;font-weight:600}
</style>
</head>
<body>
<div id="welcome" class="warn" style="display:none">
  <div>👋 Welcome to CtxEng AI</div>
  <div style="margin:6px 0">To use Ask AI, add at least one API key:</div>
  <div class="row"><button id="welcomeAddKey" class="primary">+ Add API Key</button><button id="welcomeDismiss">Dismiss</button></div>
  <div>Or install Ollama for free local AI: <a href="#" id="ollamaLink">Open Ollama Website</a></div>
  <div>Build Context and Explain File work without any API key. ✅</div>
</div>

<div class="row">
  <select id="providerSelect" style="flex:1"></select>
  <input id="openRouterModel" style="display:none;flex:1" />
  <select id="modelSelect" style="flex:1"></select>
  <button id="setKeyBtn">🔑 Set Key</button>
</div>

<div id="inlineWarning" class="warn" style="display:none"></div>
<div class="row"><input id="queryInput" style="flex:1" placeholder="Ask something about your codebase..."/></div>
<div class="row">
  <button id="buildBtn" class="primary">Build Context</button>
  <button id="askBtn" class="primary">Ask AI</button>
  <button id="explainBtn">Explain Current File</button>
  <button id="diffBtn">Show Diff</button>
</div>
<div id="loadingBox" class="warn" style="display:none"></div>
<div id="errorBox" class="error" style="display:none"></div>

<div class="section">
  <div class="title">Metrics</div>
  <div class="metrics">
    <div class="metric"><div class="k">Tokens</div><div id="tokenStat" class="v">-</div></div>
    <div class="metric"><div class="k">Cost</div><div id="costStat" class="v">-</div></div>
    <div class="metric"><div class="k">Files</div><div id="fileStat" class="v">-</div></div>
  </div>
</div>

<div class="section"><div class="title">📄 Selected Files</div><div id="selectedFiles" class="list"></div></div>
<div class="section"><div class="title">⚠️ Skipped Files</div><div id="skippedFiles" class="list"></div></div>
<div class="section"><div class="title">🧠 Context Preview</div><div id="preview" class="preview"></div></div>
<div class="section"><div class="title">🤖 AI Response</div><div id="response" class="response"></div></div>

<script nonce="${nonce}">
const vscode = acquireVsCodeApi();
const state = { providers: [], configuredProviderIds: [], activeProviderId: '', activeModel: '', openRouterModel: '', ollamaReachable: false, ollamaModels: [], contextMarkdown: '', aiResponse: '', loading: 'idle' };
const $ = (id) => document.getElementById(id);

function esc(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function renderMd(md){return md.split(/\r?\n/).map(l=>'<div>'+esc(l)+'</div>').join('');}
function showError(msg){const e=$('errorBox'); e.textContent=msg; e.style.display='block';}
function clearError(){const e=$('errorBox'); e.textContent=''; e.style.display='none';}
function setLoading(kind){ state.loading=kind; const box=$('loadingBox'); const on=kind!=='idle'; box.style.display=on?'block':'none'; box.textContent=kind==='build'?'⏳ Building context...':(kind==='ask'?'⏳ Asking AI...':''); ['buildBtn','askBtn','explainBtn','diffBtn','providerSelect','modelSelect','openRouterModel','setKeyBtn'].forEach(id=>{const el=$(id); if(el) el.disabled=on;}); if(!on) syncProviderUi(); }
function status(id){ if(id==='ollama') return 'green'; return state.configuredProviderIds.includes(id)?'green':'red'; }

function syncProviderUi(){
 const sel=$('providerSelect'); sel.innerHTML='';
 const greens=state.providers.filter(p=>status(p.id)==='green' || p.id==='ollama');
 const reds=state.providers.filter(p=>!greens.some(g=>g.id===p.id));
 const add=(p,red)=>{const o=document.createElement('option'); o.value=p.id; o.textContent=(p.id==='ollama'?'⚡':(red?'🔴':'🟢'))+' '+p.displayName; if(red) o.style.opacity='0.5'; sel.appendChild(o);};
 greens.forEach(p=>add(p,false)); if(reds.length){const sep=document.createElement('option'); sep.disabled=true; sep.textContent='──────────'; sel.appendChild(sep); reds.forEach(p=>add(p,true));}
 sel.value = state.activeProviderId || greens[0]?.id || state.providers[0]?.id || '';
 const p=state.providers.find(x=>x.id===sel.value);
 const msel=$('modelSelect'); const oInput=$('openRouterModel'); msel.innerHTML='';
 const models=p?.id==='ollama'?state.ollamaModels:(p?.models||[]);
 if(p?.id==='openrouter'){ oInput.style.display='block'; msel.style.display='none'; oInput.value=state.openRouterModel||''; }
 else { oInput.style.display='none'; msel.style.display='block'; models.forEach(m=>{const o=document.createElement('option'); o.value=m; o.textContent=m; msel.appendChild(o);}); if(models.length) msel.value=models.includes(state.activeModel)?state.activeModel:models[0]; }
 const askOk = p ? (status(p.id)==='green' || p.id==='ollama') : false;
 $('askBtn').disabled = state.loading!=='idle' || !askOk;
 $('askBtn').title = askOk ? '' : 'No API key configured for this provider';
 if(!askOk && p){ $('inlineWarning').style.display='block'; $('inlineWarning').innerHTML = '⚠️ No API key for '+p.displayName+'. <button id="inlineSet">Set Key</button> <button id="inlineDismiss">Dismiss</button>'; $('inlineSet').onclick=()=>vscode.postMessage({type:'setApiKey', providerId:p.id}); $('inlineDismiss').onclick=()=>vscode.postMessage({type:'dismissInlineWarning'}); }
 else { $('inlineWarning').style.display='none'; }
}

function renderSelected(items){
 const el=$('selectedFiles'); el.innerHTML=''; if(!items.length){el.innerHTML='<div>None</div>'; return;}
 for(const f of items){const row=document.createElement('div'); row.className='file'; const btn=document.createElement('button'); btn.className='file-btn'; btn.textContent=f.path; btn.onclick=()=>vscode.postMessage({type:'openFile', path:f.path}); const bar=document.createElement('div'); bar.className='bar'; const fill=document.createElement('span'); fill.style.width=Math.max(0,Math.min(100,f.score*100))+'%'; bar.appendChild(fill); const s=document.createElement('div'); s.textContent=f.score.toFixed(2); s.style.width='36px'; s.style.textAlign='right'; row.append(btn,bar,s); el.appendChild(row);} }
function renderSkipped(items,count){const el=$('skippedFiles'); el.innerHTML=''; if(!items.length){el.innerHTML='<div>Skipped: '+count+' files</div>'; return;} items.forEach(i=>{const d=document.createElement('div'); d.textContent=i; d.style.opacity='0.7'; el.appendChild(d);});}

$('buildBtn').onclick=()=>{clearError();vscode.postMessage({type:'buildContext',query:$('queryInput').value||''});};
$('explainBtn').onclick=()=>{clearError();vscode.postMessage({type:'explainCurrentFile',query:$('queryInput').value||''});};
$('askBtn').onclick=()=>{clearError(); const providerId=$('providerSelect').value; const model=providerId==='openrouter' ? $('openRouterModel').value : $('modelSelect').value; vscode.postMessage({type:'askAi',query:$('queryInput').value||'',providerId,model,context:state.contextMarkdown||''});};
$('diffBtn').onclick=()=>{ if(!state.aiResponse.trim()){showError('❌ No AI response to diff yet.'); return;} vscode.postMessage({type:'openDiff', suggestedText:state.aiResponse}); };
$('providerSelect').onchange=()=>{ state.activeProviderId=$('providerSelect').value; const model=state.activeProviderId==='openrouter' ? $('openRouterModel').value : $('modelSelect').value; vscode.postMessage({type:'providerChanged', providerId:state.activeProviderId, model}); syncProviderUi(); };
$('modelSelect').onchange=()=>{ state.activeModel=$('modelSelect').value; vscode.postMessage({type:'providerChanged', providerId:$('providerSelect').value, model:$('modelSelect').value}); };
$('openRouterModel').onchange=()=>{ state.openRouterModel=$('openRouterModel').value; vscode.postMessage({type:'providerChanged', providerId:'openrouter', model:$('openRouterModel').value}); };
$('setKeyBtn').onclick=()=>vscode.postMessage({type:'setApiKey', providerId:$('providerSelect').value});
$('welcomeAddKey').onclick=()=>vscode.postMessage({type:'setApiKey', providerId:$('providerSelect').value});
$('welcomeDismiss').onclick=()=>vscode.postMessage({type:'dismissWelcome'});
$('ollamaLink').onclick=(e)=>{e.preventDefault();vscode.postMessage({type:'openOllamaWebsite'});};

window.addEventListener('message',(event)=>{
 const msg=event.data;
 if(msg.type==='state'){ Object.assign(state,msg.state); syncProviderUi(); $('welcome').style.display = (!state.welcomeDismissed && state.configuredProviderIds.length===0 && !state.ollamaReachable)?'block':'none'; }
 if(msg.type==='inlineWarning'){ if(msg.message){ $('inlineWarning').style.display='block'; $('inlineWarning').textContent=msg.message; } else $('inlineWarning').style.display='none'; }
 if(msg.type==='loading'){ setLoading(msg.kind||'idle'); }
 if(msg.type==='error'){ showError(msg.message); setLoading('idle'); }
 if(msg.type==='buildResult'){ const p=msg.payload; renderSelected(p.summary.includedFiles||[]); renderSkipped(p.summary.skippedFiles||[], p.summary.skippedCount||0); $('tokenStat').textContent = String(p.summary.tokenCount ?? '-'); $('costStat').textContent = p.summary.costEstimate!=null?('$'+Number(p.summary.costEstimate).toFixed(3)):'-'; $('fileStat').textContent = String((p.summary.includedFiles||[]).length); state.contextMarkdown=p.contextMarkdown||''; $('preview').innerHTML=renderMd(state.contextMarkdown); }
 if(msg.type==='aiStart'){ state.aiResponse=''; $('response').textContent=''; }
 if(msg.type==='aiChunk'){ state.aiResponse += msg.chunk; $('response').textContent += msg.chunk; $('response').scrollTop = $('response').scrollHeight; }
 if(msg.type==='aiDone'){ setLoading('idle'); }
});

vscode.postMessage({type:'ready'});
</script>
</body>
</html>`;
  }
}
