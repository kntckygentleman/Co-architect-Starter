# Co-Architect Starter

Most AI coding tools default to flattering you, writing padded corporate prose, and forgetting key decisions as soon as a thread grows long. **Co-Architect Starter** fixes those failure modes with a portable, zero-dependency Python kit (`Python 3.9+` standard library only). Instead of another agreeable assistant, it builds a structured working partner calibrated to balance your blind spots, backed by deterministic rules that check every file write and shell command before execution.

It runs across **Claude Code**, **Cursor**, **Codex CLI**, **Windsurf**, **Cline**, **Google Antigravity**, and any editor that reads `AGENTS.md`. Out of the box, canonical long-term memory stays in plain local Markdown versioned by Git (`ssot/00_STATE_PROJECT_CANON.md`), and you can point that memory layer at Obsidian, Notion, Google Drive, SQLite/Postgres, or NotebookLM with a single flag.

See [`llms.txt`](llms.txt) for a structured index that coding agents can parse directly. For the multi-workspace production reference behind these patterns, see [`Cognitive-Function-Based-Architecture`](https://github.com/kntckygentleman/Cognitive-Function-Based-Architecture).

---

## Quick Start (One-Paste Setup)

Clone the repository, open it in your preferred AI coding tool, and paste:

> **Read `AGENTS.md` (or `CLAUDE.md` / `GEMINI.md`) and walk me through setting up my Co-Architect workspace.**

Your agent inspects your OS, shell, timezone, and installed tools with `bootstrap.py detect`, asks how you prefer to think and work (either your known MBTI + Enneagram or a short 6-question diagnostic), asks where you want long-term notes stored, builds the workspace, and verifies all checks pass before handing control back to you.

---

## Supported Agent Platforms (`--platform`)

Every build always creates universal `SYSTEM_PROMPT.md`, `AGENTS.md`, `.agents/hooks.json`, and `.agents/rules/state-hydration.md`. Choose `--platform auto` (default, configures detected tools) or pass an explicit target:

| `--platform` | Generated Files | Enforcement Mechanism |
|---|---|---|
| `auto` (default) | Universal files + detected runtimes | Matches installed Antigravity, Claude Code, Cursor, Codex, or Windsurf |
| `all` | All platform entrypoints below | Configures every supported IDE and CLI side by side |
| `claude` | `CLAUDE.md` + `.claude/settings.json` | Native `SessionStart`, `PreToolUse` (exit code `2` block), and `PostToolUse` |
| `cursor` | `AGENTS.md` + `.cursor/rules/coarchitect.mdc` | Always-applied `.mdc` rules + `workspace_hooks.py check-files` |
| `antigravity` | `GEMINI.md` + `.agents/hooks.json` | Native Antigravity `SessionStart`, `PreToolUse`, and `PostToolUse` |
| `codex` / `generic` | `AGENTS.md` + `SYSTEM_PROMPT.md` | Works with `--install-git-hook` (`.git/hooks/pre-commit`) in any shell workflow |

---

## Pluggable Single Source of Truth (`--ssot`)

Co-Architect separates durable long-form memory (SSoT) from compact working caches in `state/*.md` (`<100` lines each):

| `--ssot` | Backend | Default `--ssot-target` |
|---|---|---|
| `local` (default) | Plain Markdown + Git (created during build) | `ssot/00_STATE_PROJECT_CANON.md` |
| `obsidian` | Local Obsidian vault notes | `Vault/00_STATE_PROJECT_CANON.md` |
| `notion` | Notion workspace pages via MCP or API | `Notion:Project-Canon` |
| `gdrive` | Google Drive / Docs via CLI or MCP | `Drive:00_PROJECT_CANON` |
| `sql` | SQLite or PostgreSQL ledger | `sqlite:///ssot/canon.db` |
| `notebooklm` | NotebookLM via Kortex MCP | Notebook UUID |
| `custom` | Any external database or wiki endpoint | `custom://ssot` |

---

## Manual CLI Examples

```bash
# 1. Inspect detected OS, Python version, shell, timezone, and installed agent runtimes
python3 bootstrap.py detect

# 2. Build for Claude Code + Cursor with an Obsidian vault target and a Git pre-commit hook
python3 bootstrap.py build \
  --target-dir . \
  --mbti ENTP \
  --enneagram 7w8 \
  --instincts sp/sx \
  --operator-name Alex \
  --platform all \
  --ssot obsidian \
  --ssot-target "~/Documents/Obsidian/ProjectCanon.md" \
  --domains "Backend Architecture, Technical Writing" \
  --install-git-hook

# 3. Preview without writing files, or print the 6-dilemma quiz
python3 bootstrap.py grill --format text
python3 bootstrap.py preview --mbti INFP --enneagram 4w5 --instincts sx/sp --ssot local

# 4. Run file checks manually in CI or any editor without native PreToolUse hooks
python3 .agents/scripts/workspace_hooks.py check-files README.md state/active_sprint.md

# 5. Reset the repository back to clean unconfigured Bootstrap Mode
python3 bootstrap.py reset-bootstrap --target-dir . --confirm
```

---

## What the Starter Enforces in Code

Prompt instructions drift over long conversations, so critical invariants are enforced in [`core_hooks.py`](.agents/scripts/core_hooks.py) and [`workspace_hooks.py`](.agents/scripts/workspace_hooks.py):

1. **Core Architecture Lock:** Blocks silent edits to `SYSTEM_PROMPT.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/settings.json`, `.cursor/rules/coarchitect.mdc`, and `.agents/` scripts unless your prompt begins with the workspace debug passphrase (or `COARCHITECT_DEBUG=1` in Git pre-commit).
2. **Anti-Slop & Security Checks:** Rejects hidden Unicode / bidi overrides, prompt-injection tags in cached state, secret/`.env` shell inspection, em/en dashes, negative-positive framing, and banned filler phrases before a file write lands.
3. **Cross-Platform Payload Normalization:** `normalize_hook_payload()` translates both Antigravity `toolCall` JSON and Claude Code `Write`/`Edit`/`MultiEdit`/`Read`/`Bash`/`Task`/`Agent`/`WebSearch`/`WebFetch` hook payloads through one verification path, returning exit code `2` and `hookSpecificOutput` JSON on Claude Code denies.
4. **Tamper-Evident Audit Chain:** [`audit_log.py`](.agents/scripts/audit_log.py) appends every tool execution and architectural decision to `state/audit_log.jsonl` with linked SHA-256 hashes.
5. **Adversarial Review Tools (`/council` & `/iterate`):** Includes a 7-seat Veil-of-Ignorance review council and an isolated staging runner (`iterate_stage.py`) so proposals can go through clean-room critique before modifying live workspace files.

---

## Verification

```bash
python3 -m unittest discover -s tests -v
```
