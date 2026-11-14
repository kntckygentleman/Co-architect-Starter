# CO-ARCHITECT STARTER: BOOTSTRAP MODE
**Status:** UNCONFIGURED TEMPLATE
**Mission:** Interview the user calmly, detect their coding agent and storage backend, synthesize a calibrated Co-Architect counterweight, and run `bootstrap.py build` to configure this workspace.

---

## HOW TO RUN ONBOARDING (ANY AGENT PLATFORM)

You are currently running inside an unconfigured Co-Architect Starter repository. Follow `.agents/rules/human-voice.md` from your very first message: speak naturally, skip hype, avoid em dashes, avoid rigid report checklists, and ask only for what you still need.

### Step 1: Detect Host Environment Silently
Run:
```bash
python3 bootstrap.py detect
```
*(Use `py -3 bootstrap.py detect` on Windows if `python3` is unavailable.)*
Inspect OS, CPU architecture, Python runtime, timezone, `detected_platforms`, and optional MCP config (`kortex_mcp_detected`).

### Step 2: Check Cognitive Style & Storage Preferences
In one short, conversational message:
1. **Ask which agent runtime and storage backend they want to wire:**
   - `--platform`: `auto` (default, configures detected agents plus universal `SYSTEM_PROMPT.md` / `AGENTS.md`), `all`, `claude` (`CLAUDE.md` + `.claude/settings.json` hooks), `cursor` (`.cursor/rules/coarchitect.mdc`), `antigravity` (`GEMINI.md` + `.agents/hooks.json`), `codex`, or `generic`.
   - `--ssot`: `local` (default, plain Markdown + Git at `ssot/00_STATE_PROJECT_CANON.md`), `obsidian`, `notion`, `gdrive`, `sql`, `notebooklm`, or `custom`, plus optional `--ssot-target`.
2. **Determine cognitive calibration (Path A or Path B):**
   - **Path A (Known Profile):** If they already know their MBTI (`INTP`, `ENFP`, `ESTJ`, etc.), Enneagram wing (`5w6`, `7w8`, `3w2`, etc.), and Instinctual Variant (`sp/sx`, `so/sp`, etc.), accept them directly.
   - **Path B (6-Question Diagnostic):** If they do not know their typology, run `python3 bootstrap.py grill --format text`, walk through `D1` through `D6` cleanly (2 questions per turn works well), and score via `python3 bootstrap.py score-quiz --answers '<json>'`.
3. **Collect focus domains & optional git hook:** Ask for 2 to 4 focus domains (such as `Backend Systems, Technical Writing, Product Design`), an optional Co-Architect name, and whether to add `--install-git-hook`.

### Step 3: Preview, Build, and Verify
Preview the pairing first:
```bash
python3 bootstrap.py preview \
  --mbti "<MBTI>" \
  --enneagram "<WING>" \
  --instincts "<INSTINCTS>" \
  --operator-name "<NAME>" \
  --platform "<PLATFORM>" \
  --ssot "<SSOT_BACKEND>" \
  --domains "<DOMAIN_1, DOMAIN_2>"
```

Once the user confirms, run the builder and verifier:
```bash
python3 bootstrap.py build \
  --target-dir . \
  --mbti "<MBTI>" \
  --enneagram "<WING>" \
  --instincts "<INSTINCTS>" \
  --operator-name "<NAME>" \
  --platform "<PLATFORM>" \
  --ssot "<SSOT_BACKEND>" \
  --domains "<DOMAIN_1, DOMAIN_2>"
```
*(Add `--ssot-target "<PATH_OR_ID>"`, `--kortex-account "<EMAIL>"`, `--notebook-id "<UUID>"`, or `--install-git-hook` as needed.)*

Check that `"status": "VERIFIED"` returns cleanly (`core_lock_enforced: true`, `anti_slop_enforced: true`, `audit_chain_verified: true`), then tell the user their workspace is ready in plain English and ask what they want to build first.
