import { exec, ExecOptions } from "node:child_process";
import * as path from "node:path";

export interface IncludedFileScore {
  path: string;
  score: number;
}

export interface ParsedSummary {
  includedFiles: IncludedFileScore[];
  skippedFiles: string[];
  skippedCount: number;
  tokenCount?: number;
  costEstimate?: number;
  rawStderr: string;
}

export interface BuildResult {
  stdout: string;
  stderr: string;
  summary: ParsedSummary;
}

export interface BuildOptions {
  cwd: string;
  model: string;
  format: "xml" | "markdown" | "plain";
  query: string;
  files?: string[];
}

export function runCtxeng(command: string, cwd: string): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const options: ExecOptions = { cwd, maxBuffer: 10 * 1024 * 1024 };
    exec(command, options, (error, stdoutRaw, stderrRaw) => {
      const stdout = String(stdoutRaw ?? "");
      const stderr = String(stderrRaw ?? "");
      if (error && !stdout) {
        reject(new Error(stderr || error.message));
      } else {
        resolve({ stdout, stderr });
      }
    });
  });
}

function q(v: string): string {
  return `"${v.replace(/"/g, '\\"')}"`;
}

export async function buildContext(options: BuildOptions): Promise<BuildResult> {
  const args: string[] = [
    "ctxeng",
    "build",
    q(options.query),
    "--model",
    q(options.model),
    "--fmt",
    q(options.format),
  ];
  if (options.files && options.files.length > 0) {
    args.push("--files");
    for (const file of options.files) {
      args.push(q(file));
    }
  }

  const command = args.join(" ");
  const result = await runCtxeng(command, options.cwd);
  return {
    ...result,
    summary: parseStderr(result.stderr),
  };
}

export async function explainCurrentFile(options: BuildOptions, currentFileFsPath: string): Promise<BuildResult> {
  const relPath = path.relative(options.cwd, currentFileFsPath) || currentFileFsPath;
  return buildContext({
    ...options,
    files: [relPath],
  });
}

export function parseStderr(stderr: string): ParsedSummary {
  const includedFiles: IncludedFileScore[] = [];
  const skippedFiles: string[] = [];

  const includedRegex = /\[█+\s*\]\s*([\d.]+)\s+(.+)/g;
  for (;;) {
    const m = includedRegex.exec(stderr);
    if (!m) {
      break;
    }
    const score = Number(m[1]);
    const filePath = m[2].trim();
    if (Number.isFinite(score) && filePath.length > 0) {
      includedFiles.push({ path: filePath, score });
    }
  }

  // Optional skipped filename lines if CLI ever emits them.
  const skippedNameRegex = /Skipped file:\s+(.+)/gi;
  for (;;) {
    const m = skippedNameRegex.exec(stderr);
    if (!m) {
      break;
    }
    const name = m[1].trim();
    if (name) {
      skippedFiles.push(name);
    }
  }

  const skippedCountMatch = stderr.match(/Skipped\s*:\s*(\d+)\s+files?/i);
  const skippedCount = skippedCountMatch ? Number(skippedCountMatch[1]) : 0;

  const tokenMatch = stderr.match(/Context summary \(([\d,]+)\s+tokens/i);
  const tokenCount = tokenMatch ? Number(tokenMatch[1].replace(/,/g, "")) : undefined;

  const costMatch = stderr.match(/~\$(\d+(?:\.\d+)?)/i);
  const costEstimate = costMatch ? Number(costMatch[1]) : undefined;

  return {
    includedFiles,
    skippedFiles,
    skippedCount,
    tokenCount: Number.isFinite(tokenCount ?? NaN) ? tokenCount : undefined,
    costEstimate: Number.isFinite(costEstimate ?? NaN) ? costEstimate : undefined,
    rawStderr: stderr,
  };
}

