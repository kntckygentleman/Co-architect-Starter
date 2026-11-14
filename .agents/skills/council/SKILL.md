---
name: council
description: >-
  Convene the 7-seat Impartial Adversarial Agent Council via /council (or
  wing/seat filters) under a strict Veil of Ignorance across Rational (INTJ,
  INTP, ENTJ), Human/Somatic (ENFJ, ISTJ, ISFP), and 0.5x Devil's Advocate (ENTP 8w7) seats.
---

# Impartial Adversarial Council Protocol (`/council`)

1. **Seat Selection:**
   - `/council` (default): All 7 seats (`council-intj`, `council-intp`, `council-entj`, `council-enfj`, `council-istj`, `council-isfp` at `1.0x` + `council-entp` at `0.5x`).
   - `/council rational`: `council-intj`, `council-intp`, `council-entj`, `council-entp` (`0.5x`).
   - `/council human`: `council-enfj`, `council-istj`, `council-isfp`, `council-entp` (`0.5x`).
   - `/council <seat>`: Named seat(s) only (`intj`, `intp`, `entj`, `enfj`, `istj`, `isfp`, `entp`).
   - Read [personas.md](./references/personas.md) on demand for the selected `SystemPrompt` blocks.

2. **Anonymized Bailiff Brief (`<150` Words, Zero Subagent SSoT/MCP Calls):**
   - Gather any needed local file or SSoT facts in the parent session first.
   - Strip all personal names, cognitive typology labels, and workspace lore. State the factual constraints, resource bounds, and proposal neutrally as an anonymous citizen's scenario.

3. **Clean-Room Registration & Parallel Dispatch (`Model: "pro"` Ceiling; Operator-Gated Inheritance):**
   - Register needed seats once per session as read-only subagents (`define_subagent` with `EnableMCPTools: false`, `EnableWriteTools: false`, `EnableSubagentTools: false`, or read-only `Task`/`Agent` profiles).
   - Dispatch all selected seats in parallel via `invoke_subagent` (`Workspace: "inherit"`, `Model: "pro"`, `Prompt: <Anonymized Case Brief>`) or Claude Code `Task`/`Agent` (`model: "sonnet"`). Because `Model: "inherit"` (or `opus` subagents) clones frontier planning capacity across all spawned seats, `core_hooks.py` blocks `Model: "inherit"` unless the operator's current prompt explicitly includes `--deep`, `[DEEP_COUNCIL]`, or `[CARBON_INHERIT]` alongside `[DEEP_COUNCIL]` in the subagent prompt.

4. **Weighted Synthesis & Cross-Examination:**
   - Weigh the 6 primary seats at `1.0x` and `council-entp` (mandatory Devil's Advocate dissent) at `0.5x` (elevate `council-entp` to `1.0x` whenever it catches a concrete flaw missed by the primary seats).
   - Never average competing views into bland mush: highlight the sharp splits, note any contrast between the impartial seats and your own dyadic Co-Architect view, and state your concrete recommendation.
   - Retain each seat's `conversationId` and route follow-up challenges via `send_message`.
