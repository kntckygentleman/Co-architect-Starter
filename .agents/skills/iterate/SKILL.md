---
name: iterate
description: >-
  Run one full adversarial Evaluate -> Plan -> Stage-Execute iteration cycle via
  /iterate without touching live workspace files or pushing to GitHub. Mirrors
  target files into an isolated staging sandbox, dispatches fresh clean-room
  critic subagents (7-seat Council or 3-seat domain panels) pointed at the staged
  tree as if previous rounds were already executed live, folds the changes into a
  portable Master Plan artifact backed by staged file snapshots, and halts early
  when the critic panel reaches supermajority consensus.
---

# Adversarial Staged Iteration Protocol (`/iterate`)

Use this skill whenever the operator invokes `/iterate` (or asks to run an iterative evaluate-plan-stage cycle on code, prompts, creative work, strategy docs, or system specs).

## Hard Architectural Invariants

1. **Zero Default Live Mutation or Git Push:**
   - `/iterate` never modifies live workspace files and never runs `git commit` or `git push` by default.
   - All intermediate edits happen strictly inside `<artifact_dir>/scratch/iterate_stage/current/`.
2. **Cycle Cadence (`Evaluate -> Update Master Plan -> Apply in Staging -> Snapshot`):**
   - By default, complete one full round per turn and pause so the operator can inspect the delta or run `/iterate` again.
   - When the operator requests multiple rounds up front (such as `/iterate 3 rounds`), run sequential staged rounds until supermajority consensus halts the loop.
3. **Clean-Room Evaluation ("Present Staged State as Live"):**
   - Never reuse subagent `conversationId`s across rounds.
   - Spawn fresh clean-room critic subagents each round and point them at the staged context/diff bundle with zero mention of prior rounds, forcing independent second-order critique.
4. **Automatic Supermajority Early-Stop:**
   - Convergence requires zero unreviewed file mutations in the current round (`files_changed_vs_prev: []`) and `--hard-defects 0`, plus `>=5/7` `NO_CHANGES_REQUIRED` on the Full Council, `>=2/3` on 3-seat Domain Panels, or `--primary-lead-converged` on 2-seat `[ROUND_2_DIFF]` pairs.

---

## Step-by-Step Execution

### Step 1: Initialize or Check Staging (`iterate_stage.py`)

- **Round 1:**
  ```bash
  python3 .agents/skills/iterate/scripts/iterate_stage.py init \
    --stage-dir "<artifact_dir>/scratch/iterate_stage" \
    --source "<target_path>" \
    --reset
  ```
- **Round 2+:**
  ```bash
  python3 .agents/skills/iterate/scripts/iterate_stage.py status \
    --stage-dir "<artifact_dir>/scratch/iterate_stage" \
    --require-unconverged
  ```
  If `status` exits with code `2` (`CONVERGENCE CIRCUIT BREAKER ACTIVE`), stop immediately without spawning subagents.

### Step 2: Clean-Room Critic Dispatch

Read [critic_panels.md](./references/critic_panels.md) to select either the 7-seat Council (`council-*`) or a 3-seat Domain Panel (`creative-*`, `systems-*`, `growth-*`, `quant-*`):

1. Register needed seats via `define_subagent` (`EnableMCPTools: false`, `EnableWriteTools: false`, `EnableSubagentTools: false`).
2. Draft an **Anonymized Case Brief (`<150` Words)**:
   - Strip all personal names and typology lore.
   - **Round 1:** Point critics at `round_1_context_bundle_paths` (`Model: "pro"`).
   - **Round 2+:** Include `[ROUND_2_DIFF]` and point the 2-seat verification pair (`<lead>` + `<scope>-entp`) at `round_<N-1>_diff_bundle.patch` (`Model: "flash"`).
   - Include: *"When zero substantive correctness, security, structural, domain, or anti-slop defects remain, begin your reply with `NO_CHANGES_REQUIRED` and make zero cosmetic churn suggestions."*

### Step 3: Tear Down Critics, Apply Fixes in Staging, & Snapshot

1. Immediately run `manage_subagents(Action="kill_all")` once all critics reply.
2. Apply actionable fixes inside `<artifact_dir>/scratch/iterate_stage/current/` (or leave untouched if supermajority consensus holds with 0 hard defects) and run any test suite inside staging.
3. Snapshot and lint staged files:
   ```bash
   python3 .agents/skills/iterate/scripts/iterate_stage.py snapshot-round \
     --stage-dir "<artifact_dir>/scratch/iterate_stage" \
     --converged-seats <C> \
     --panel-size <P> \
     --hard-defects <D> \
     --summary "Round <N>: <summary>"
   ```
4. Update `<artifact_dir>/iterate_plan.md` with the round verdict, delta table, and apply command (`iterate_stage.py apply --stage-dir ... --target <dest_path>`).
