# Co-Architect Starter

**Self-Assembling Dyadic AI Co-Architect, Cross-Platform Deterministic Anti-Slop Harness, SHA-256 Provenance Ledger, and Veil-of-Ignorance Adversarial Council (`/council` & `/iterate`) for Google Antigravity.**

Zero external dependencies (Python 3.9+ standard library only). Auto-configures across **macOS** (`arm64` / `x86_64`), **Linux / WSL2**, and **Windows 10/11**.

---

## Fastest Setup: Drop in the Link & Let Antigravity Build It

You do not need to edit config files by hand. Open Google Antigravity in an empty workspace folder (or an existing workspace), paste one of the prompts below, grant terminal permission when asked, and let the Bootstrap Agent handle the rest:

### Option A: You Don't Know Your Typology (Interactive 6-Question Grilling)
> Clone `https://github.com/kntckygentleman/Co-architect-Starter.git` into this workspace (or inspect it here) and follow its `GEMINI.md` bootstrap flow. Detect my machine architecture, run the 6-question cognitive diagnostic interview with me, and build my custom Co-Architect and anti-slop harness automatically.

### Option B: You Already Know Your Stack (Direct One-Pass Build)
> Clone `https://github.com/kntckygentleman/Co-architect-Starter.git` into this workspace (or inspect it here) and follow its `GEMINI.md` bootstrap flow. My profile is `<MBTI> <Enneagram> <Instincts>` (for example, `ENTP 4w3 so/sp`), my name is `<Name>`, and my main focus areas are `<Domains>`. Detect my machine, build my custom Co-Architect and harness, and verify the installation.

---

## What Gets Built Automatically

1. **Personalized Dyadic Co-Architect (`GEMINI.md` & `SYSTEM_PROMPT.md`):**
   - Synthesizes a complementary counterweight stack across all 16 Jungian function stacks, 9 Enneagram cores/wings, and 6 instinctual stackings under an explicit **`Observed Reality > Typology Heuristic`** rule (see [`docs/COGNITIVE_PAIRING_FRAMEWORK.md`](./docs/COGNITIVE_PAIRING_FRAMEWORK.md)).
   - Enforces a **Two-Volley Debate Cap** (settling Turn-3 disagreements with a 15-minute empirical test) and a `[SANDBOX]` escape hatch for zero-commitment experiments.
2. **Cross-Platform Deterministic Python Hooks (`.agents/hooks.json` + `core_hooks.py`):**
   - Inspects the host OS (`Darwin`, `Linux`, `Windows`), resolves the local Python binary and file-locking primitive (`fcntl` on POSIX, `msvcrt` on Windows), and writes `.agents/hooks.json` with exact machine paths.
   - **Preventive Anti-Slop Gate (`PreToolUse`):** Blocks Markdown writes containing em dashes, en dashes, negative-positive contrast formulas, unparsed pseudo-weights, or LLM filler vocabulary defined in [`.agents/rules/human-voice.md`](./.agents/rules/human-voice.md).
   - **Core Architecture Lock (`PreToolUse`):** Protects `GEMINI.md`, `SYSTEM_PROMPT.md`, hooks, rules, and skills against accidental or prompt-injected edits unless your prompt begins with `[<ArchitectName> Debug Mode]`.
   - **Security & Quota Gates (`PreToolUse`):** Blocks invisible zero-width/bidi Unicode injection, protects `.env` and host credential files from shell inspection, tracks CaMeL untrusted-input taint, and enforces explicit subagent model tiering (`flash` for workers/diffs, `pro` for panels, gated `inherit`).
3. **Two-Tier Compact State & SHA-256 Hash-Chained Provenance (`state/` & `audit_log.py`):**
   - Initializes compact `<100`-line Turn-0 state caches (`operator_profile.md`, `routing_matrix.md`, `active_sprint.md`, `archive_decisions.md`) audited at `SessionStart`.
   - Logs every tool call, file hash delta, and Architectural Decision Record (`ADR-XXXX`) to a tamper-evident SHA-256 hash chain (`state/audit_log.jsonl`).
4. **7-Seat Rawlsian Veil-of-Ignorance Council (`/council`) & Clean-Room Iteration (`/iterate`):**
   - `/council` dispatches 6 impartial `1.0x` cognitive perspectives (`INTJ`, `INTP`, `ENTJ`, `ENFJ`, `ISTJ`, `ISFP`) plus a mandatory `0.5x` Devil's Advocate (`ENTP`) on anonymized `<150`-word briefs stripped of personal names and history.
   - `/iterate` mirrors target files into an isolated clean-room sandbox (`iterate_stage.py`), dispatches fresh critics on `<760`-line context shards and unified diff patches, and halts automatically upon supermajority consensus.

---

## Direct Terminal CLI Usage (Optional)

If you prefer running the installer directly from a terminal:

```bash
# 1. Inspect detected host OS, Python invoker, lock backend, and timezone
python3 bootstrap.py detect

# 2. Preview a pairing without writing files
python3 bootstrap.py preview --operator-name "Alex" --mbti ENTP --enneagram 4w3 --instincts so/sp

# 3. Build in place (or pass --target-dir /path/to/workspace) and run live self-verification
python3 bootstrap.py build \
  --operator-name "Alex" \
  --mbti ENTP \
  --enneagram 4w3 \
  --instincts so/sp \
  --architect-name "Vera" \
  --domains "Creative Projects, Events & Social Calendar, Career Strategy"

# 4. Run the zero-dependency automated test suite (macOS / Linux / Windows)
python3 -m unittest discover -s tests -v
```

---

## Repository Layout

```text
coarchitect-starter/
├── README.md                                  # Quickstart & architecture overview
├── GEMINI.md                                  # Starts in Bootstrap Mode; becomes your custom Co-Architect on build
├── bootstrap.py                               # Zero-dependency CLI (detect | grill | score-quiz | preview | build | verify)
├── docs/
│   └── COGNITIVE_PAIRING_FRAMEWORK.md         # 16-type + Enneagram + Instinct counterweight specification
├── engine/
│   ├── host_probe.py                          # Cross-platform OS, Python, lock-backend & timezone inspector
│   ├── cognitive_matrix.py                    # Dyadic pairing synthesizer & 6-dilemma diagnostic scorer
│   └── renderer.py                            # Renders GEMINI.md, hooks.json, state/*.md & state hydration
├── templates/
│   └── bootstrap_gemini.md                    # Preserved copy of Bootstrap Mode onboarding instructions
├── .agents/
│   ├── rules/
│   │   └── human-voice.md                     # Anti-LLM prose & anti-slop protocol
│   ├── scripts/
│   │   ├── core_hooks.py                      # Cross-platform (fcntl / msvcrt) PreToolUse, PostToolUse & SessionStart kernel
│   │   ├── workspace_hooks.py                 # Configurable Co-Architect hook entrypoint
│   │   └── audit_log.py                       # SHA-256 hash-chain verifier, ADR recorder & token telemetry CLI
│   └── skills/
│       ├── council/                           # 7-seat Veil-of-Ignorance Council (/council)
│       └── iterate/                           # Clean-room staged iteration engine (/iterate + iterate_stage.py)
└── tests/
    └── test_bootstrap_and_harness.py          # Comprehensive cross-platform unittest suite
```
