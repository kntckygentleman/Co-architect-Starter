# DYADIC COGNITIVE COUNTERWEIGHT FRAMEWORK

This document explains how `engine/cognitive_matrix.py` pairs a human operator's baseline cognitive stack with an antagonistic-yet-cooperative AI Co-Architect.

## 1. Core Principle: `Observed Reality > Typology Heuristic`

Jungian cognitive functions (`Ni`, `Ne`, `Ti`, `Te`, `Fi`, `Fe`, `Si`, `Se`), Enneagram core/wing drives (`1w9` through `9w8`), and Instinctual stackings (`sp`, `sx`, `so`) are used strictly as **falsifiable compression labels** for operational strengths, blind spots under fatigue, and pushback preferences.

Every generated `GEMINI.md` includes an explicit empirical precedence rule: live behavior, direct user preferences, empirical benchmarks, and updates in `state/*.md` immediately outrank typological priors whenever real life diverges.

---

## 2. Jungian Counterweight Pairing Table (`16 -> 5` Architectural Archetypes)

Standard AI assistants mirror the operator's dominant habits: if the operator branches into fifteen open tabs, the assistant cheers on tab sixteen; if the operator over-architects in isolation, the assistant writes another thousand words of theory.

Instead, `cognitive_matrix.py` pairs each operator stack with a complementary counterweight stack that covers their neglected cognitive functions while respecting their core judgment axis:

| Operator MBTI | Ego Stack | Primary Blind Spot Under Load | Default Co-Architect Stack | Why the Counterweight Works |
| :--- | :--- | :--- | :--- | :--- |
| **`ENTP`** | `Ne-Ti-Fe-Si` | Lateral sprawl & dodging low-stimulus `Si` wrap-up | **`INTJ` (`Ni-Te-Fi-Se`)** | Compresses 15 lateral `Ne` branches into one durable six-month `Ni-Te` build |
| **`ENFP`** | `Ne-Fi-Te-Si` | Parallel creative over-commitment & admin stall | **`INTJ` (`Ni-Te-Fi-Se`)** | Shares `Fi-Te` to honor authentic voice while supplying steady `Ni-Te` completion |
| **`INTJ`** | `Ni-Te-Fi-Se` | Premature convergence & insulated `Ni-Fi` loops | **`ENTP` (`Ne-Ti-Fe-Si`)** | Stress-tests hidden premises (`Ti`), surfaces edge cases (`Ne`), and forces early prototypes |
| **`INFJ`** | `Ni-Fe-Ti-Se` | Over-extending for others & `7th-slot Te` pruning friction | **`ENTJ` (`Te-Ni-Se-Fi`)** | Matches `Ni` depth while supplying crisp `Te-Se` execution cuts and `Fi` boundary defense |
| **`INTP`** | `Ti-Ne-Si-Fe` | Infinite `Ti-Si` refactoring instead of shipping | **`ENTJ` (`Te-Ni-Se-Fi`)** | Respects `Ti` rigor while cutting yak-shaving and driving 14-day kinetic delivery |
| **`ISTP`** | `Ti-Se-Ni-Fe` | Isolated tactical optimization & thin multi-month docs | **`ENTJ` (`Te-Ni-Se-Fi`)** | Pairs shared `Se` realism with `Te-Ni` multi-quarter roadmapping |
| **`ENTJ`** | `Te-Ni-Se-Fi` | Optimizing an unexamined objective function at high speed | **`INTP` (`Ti-Ne-Si-Fe`)** | Audits core axioms (`Ti`) and perverse incentives (`Ne`) before capital commitment |
| **`ESTJ`** | `Te-Si-Ne-Fi` | Over-maintaining legacy workflows past regime shifts | **`INTJ` (`Ni-Te-Fi-Se`)** | Supplies long-horizon `Ni` trajectory shifts alongside `Te` execution |
| **`INFP`** | `Fi-Ne-Si-Te` | Freezing when external scaffolding feels soulless | **`INTJ` (`Ni-Te-Fi-Se`)** | Protects internal `Fi` meaning while quietly handling `Ni-Te` finish-line structure |
| **`ISFP`** | `Fi-Se-Ni-Te` | Short-horizon planning & resistance to rigid admin | **`INTJ` (`Ni-Te-Fi-Se`)** | Shares all four functions (`Ni-Te-Fi-Se`) to sequence six-month arcs without crushing craft |
| **`ENFJ`** | `Fe-Ni-Se-Ti` | Absorbing external emergencies over solo priorities | **`ISTP` (`Ti-Se-Ni-Fe`)** | Cool, unsentimental `Ti-Se` scalpel that cuts unearned obligations cleanly |
| **`ESFJ`** | `Fe-Si-Ne-Ti` | Carrying invisible admin labor & neglecting leverage | **`INTP` (`Ti-Ne-Si-Fe`)** | Defends schedule boundaries objectively (`Ti`) and widens strategic options (`Ne`) |
| **`ISTJ`** | `Si-Te-Fi-Ne` | Sunk-cost duty & under-exploring asymmetric shortcuts | **`ENTP` (`Ne-Ti-Fe-Si`)** | Challenges legacy commitments (`Ne-Ti`) before adding another routine |
| **`ISFJ`** | `Si-Fe-Ti-Ne` | Difficulty refusing low-return favors (`7th-slot Te`) | **`INTJ` (`Ni-Te-Fi-Se`)** | Supplies firm `Te` return-on-effort gates and `Ni` priority pruning |
| **`ESTP`** | `Se-Ti-Fe-Ni` | Short-horizon tactical reactivity & six-month debt | **`INTJ` (`Ni-Te-Fi-Se`)** | Shadows kinetic speed with a six-month `Ni-Te` structural radar |
| **`ESFP`** | `Se-Fi-Te-Ni` | Dropping upkeep once novelty fades (`Inferior Ni`) | **`INTJ` (`Ni-Te-Fi-Se`)** | Exact functional mirror (`Ni-Te-Fi-Se`) locking durable architecture |

Power users can also pass `--counterweight-mbti <INTJ|ENTJ|ENTP|INTP|ISTP>` to `bootstrap.py build` to select any archetype explicitly.

---

## 3. Enneagram & Instinctual Modulation

Two people with the exact same Jungian stack can have completely different relational triggers. For example, an `ENTP 8w7 sx/sp` operator and an `ENTP 4w3 so/sp` operator both benefit from `INTJ` (`Ni-Te`) scope convergence, yet require distinct counterweight calibration:

- **`ENTP 8w7 sx/sp`:** Motivated by sovereign autonomy and leverage; allergic to micromanagement (`8w7`) and group caretaking (`so`-last). Paired with **`INTJ 5w6 (with 1w9 Anchor)`**: cool, high-differentiation chess-match pushback backed by empirical receipts, protecting the `sp` foundation during intense `sx` sprints.
- **`ENTP 4w3 so/sp`:** Motivated by creative originality, aesthetic integrity, and social/cultural resonance (`4w3`, `so`-dominant), with isolated tunnel-immersion last (`sx`-last). Paired with **`INTJ 1w9 (with 5w4 Anchor)`**: composed, creatively literate structural support that honors original voice without flattening it into generic templates, while protecting uninterrupted `sx` deep-work blocks against `so/sp` schedule fragmentation.

All nine Enneagram cores (`1..9`), eighteen wings (`1w9..9w8`), and six instinct stackings (`sx/sp`, `sp/sx`, `so/sp`, `sp/so`, `sx/so`, `so/sx`) are encoded deterministically in [`engine/cognitive_matrix.py`](../engine/cognitive_matrix.py).
