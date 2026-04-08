# Changelog

## 0.1.6

- Added CtxEng AI sidebar with production webview UX and secure provider controls.
- Added loading states for context build and AI request (`Building context...`, `Asking AI...`) with disabled controls while running.
- Added real-time streaming AI response rendering for streaming-capable providers, with fallback for non-streaming providers.
- Added clickable selected-file navigation (open in editor + reveal in workspace explorer).
- Added AI suggestion diff workflow via `vscode.diff` against active selection/file.
- Added metrics dashboard for token count, estimated cost, and selected file count.
- Added provider streaming plumbing and improved extension-side state synchronization.

## 0.1.0

- Initial extension scaffold.
- Added commands:
  - `ctxeng.buildContext`
  - `ctxeng.buildContextCurrentFile`
  - `ctxeng.watchContext`
  - `ctxeng.showSummary`
- Added keybinding `Ctrl+Shift+C` for context build.
- Added configuration settings:
  - `ctxeng.model`
  - `ctxeng.format`
  - `ctxeng.autoWatch`
