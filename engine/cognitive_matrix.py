#!/usr/bin/env python3
"""Dyadic Cognitive Counterweight Matrix & 6-Dilemma Diagnostic Scorer.

Encodes the Ego <-> Healthy Counterweight pairing logic across:
1. All 16 Jungian / MBTI cognitive function stacks (Dominant, Auxiliary, Tertiary, Inferior).
2. All 9 Enneagram cores and wings (1w9..9w8) with reactance and drive calibration.
3. All 6 Instinctual Variant stackings (sp/sx, sp/so, sx/sp, sx/so, so/sp, so/sx).
4. A 6-dilemma operational diagnostic ("The Grilling") for operators who do not know their stack.

All generated prose strictly complies with `.agents/rules/human-voice.md` (zero em/en dashes,
zero negative-positive contrast frames, zero bracketed pseudo-weights, zero LLM filler terms).
"""

from __future__ import annotations

import re
from typing import Any

MBTI_STACKS: dict[str, tuple[str, str, str, str]] = {
    "ENTP": ("Ne", "Ti", "Fe", "Si"),
    "ENFP": ("Ne", "Fi", "Te", "Si"),
    "INTJ": ("Ni", "Te", "Fi", "Se"),
    "INFJ": ("Ni", "Fe", "Ti", "Se"),
    "INTP": ("Ti", "Ne", "Si", "Fe"),
    "ISTP": ("Ti", "Se", "Ni", "Fe"),
    "ENTJ": ("Te", "Ni", "Se", "Fi"),
    "ESTJ": ("Te", "Si", "Ne", "Fi"),
    "INFP": ("Fi", "Ne", "Si", "Te"),
    "ISFP": ("Fi", "Se", "Ni", "Te"),
    "ENFJ": ("Fe", "Ni", "Se", "Ti"),
    "ESFJ": ("Fe", "Si", "Ne", "Ti"),
    "ISTJ": ("Si", "Te", "Fi", "Ne"),
    "ISFJ": ("Si", "Fe", "Ti", "Ne"),
    "ESTP": ("Se", "Ti", "Fe", "Ni"),
    "ESFP": ("Se", "Fi", "Te", "Ni"),
}

OPERATOR_MBTI_PROFILES: dict[str, dict[str, str]] = {
    "ENTP": {
        "strengths": "Rapid lateral synthesis (Ne), internal logical auditing (Ti), and cross-domain pattern recognition.",
        "failure_modes": "Lateral scope sprawl, productive procrastination (starting a high-novelty puzzle to avoid low-stimulus Si wrap-up), and leaving open loops at 85 percent completion.",
        "default_counterweight": "INTJ",
        "rationale": "Pairs divergent Ne-Ti exploration with convergent Ni-Te trajectory filtering so fifteen lateral ideas compress into one durable build.",
    },
    "ENFP": {
        "strengths": "High-energy creative synthesis (Ne), strong personal conviction (Fi), and fast conceptual prototyping.",
        "failure_modes": "Over-committing to parallel creative sparks, stalling on repetitive administrative follow-through (Si), and losing momentum when external systems feel sterile.",
        "default_counterweight": "INTJ",
        "rationale": "Shares the Fi-Te judgment axis to protect authentic creative voice while inverting Ne-Si into Ni-Se convergence and steady finish-line execution.",
    },
    "INTJ": {
        "strengths": "Long-horizon architectural foresight (Ni), structural execution planning (Te), and autonomous focus.",
        "failure_modes": "Premature convergence on a single thesis, insulated Ni-Fi loops that delay live empirical contact (Se), and overlooking unanticipated lateral edge cases.",
        "default_counterweight": "ENTP",
        "rationale": "Inverts Ni-Te-Fi-Se into Ne-Ti-Fe-Si to stress-test hidden premises, surface lateral failure modes early, and force fast empirical prototypes before locking a brittle plan.",
    },
    "INFJ": {
        "strengths": "Deep pattern synthesis (Ni), high interpersonal perception (Fe), and coherent thematic vision.",
        "failure_modes": "Over-extending energy on others' priorities, perfectionistic hesitation before live action (Se), and friction around ruthless metric pruning (7th-slot Te).",
        "default_counterweight": "ENTJ",
        "rationale": "Matches Ni conceptual depth while supplying crisp Te-Se execution scaffolding and firm Fi boundary defense against external over-obligation.",
    },
    "INTP": {
        "strengths": "First-principles axiomatic precision (Ti), counterfactual edge-case discovery (Ne), and zero tolerance for conceptual hand-waving.",
        "failure_modes": "Infinite architecture refinement (Ti-Si loop), treating mental resolution as equivalent to shipping, and under-weighting concrete deadlines (Te/Se).",
        "default_counterweight": "ENTJ",
        "rationale": "Inverts Ti-Ne-Si-Fe into Te-Ni-Se-Fi to respect rigorous proofs while cutting recursive yak-shaving and driving kinetic delivery.",
    },
    "ISTP": {
        "strengths": "Mechanistic troubleshooting (Ti), calm real-time execution (Se), and lean tactical problem-solving.",
        "failure_modes": "Optimizing tactical mechanics in isolation (Ti-Ni tunnel), skipping long-horizon documentation, and deferring multi-month roadmap coordination.",
        "default_counterweight": "ENTJ",
        "rationale": "Pairs shared Se tactical realism with Te-Ni multi-quarter systems roadmapping and clean external interface specifications.",
    },
    "ENTJ": {
        "strengths": "Decisive resource allocation (Te), long-range goal alignment (Ni), and high kinetic throughput (Se).",
        "failure_modes": "Optimizing an unexamined objective function at high speed, bulldozing subtle axiomatic flaws (Ti), and overriding physical or personal recovery signals (Inferior Fi).",
        "default_counterweight": "INTP",
        "rationale": "Inverts Te-Ni-Se-Fi into Ti-Ne-Si-Fe to audit core premises before capital commitment, surface perverse incentives, and track sustainable base rates.",
    },
    "ESTJ": {
        "strengths": "Reliable operational throughput (Te), institutional consistency (Si), and clear accountability.",
        "failure_modes": "Over-optimizing legacy workflows past their useful lifespan, under-weighting asymmetric strategic shifts (Ni), and pushing past personal bandwidth limits (Fi).",
        "default_counterweight": "INTJ",
        "rationale": "Supplies long-horizon Ni regime-shift detection and Fi boundary protection alongside shared Te execution discipline.",
    },
    "INFP": {
        "strengths": "Uncompromising personal and creative integrity (Fi), rich associative ideation (Ne), and anti-performative honesty.",
        "failure_modes": "Stalling when external structure feels bureaucratic (Inferior Te), cycling in nostalgic or self-critical Fi-Si loops, and scattering energy across unfinished drafts.",
        "default_counterweight": "INTJ",
        "rationale": "Honors internal Fi conviction without corporate cheerleading while supplying quiet Ni-Te structural scaffolding that carries creative work across the finish line.",
    },
    "ISFP": {
        "strengths": "Immediate aesthetic and experiential judgment (Fi-Se), grounded craft, and zero tolerance for fake Pretense.",
        "failure_modes": "Short-horizon project planning, resistance to rigid administrative schedules (Inferior Te), and under-leveraging completed work over a six-month arc.",
        "default_counterweight": "INTJ",
        "rationale": "Shares all four cognitive functions (Ni-Te-Fi-Se) to protect tangible Fi-Se craft while organizing multi-month operational sequencing cleanly.",
    },
    "ENFJ": {
        "strengths": "High-trust coalition leadership (Fe), forward trajectory sensing (Ni), and rapid social calibration.",
        "failure_modes": "Absorbing other people's emergencies, softening hard logical cuts to preserve harmony (Inferior Ti), and starving solo strategic blocks.",
        "default_counterweight": "ISTP",
        "rationale": "Inverts Fe-Ni-Se-Ti into Ti-Se-Ni-Fe as a cool, unsentimental scalpel that audits trade-offs objectively and cuts unearned external obligations.",
    },
    "ESFJ": {
        "strengths": "Practical stewardship (Fe-Si), dependable follow-through, and high-context coordination.",
        "failure_modes": "Over-indexing on immediate group expectations, carrying invisible administrative labor, and neglecting cold structural leverage (Inferior Ti).",
        "default_counterweight": "INTP",
        "rationale": "Inverts Fe-Si-Ne-Ti into Ti-Ne-Si-Fe to defend schedule boundaries with objective logic and surface higher-return strategic options.",
    },
    "ISTJ": {
        "strengths": "High-integrity execution (Si-Te), accurate base-rate memory, and steady composure under routine load.",
        "failure_modes": "Maintaining sunk-cost obligations out of duty, under-exploring asymmetric alternatives (Inferior Ne), and absorbing slow scope creep.",
        "default_counterweight": "ENTP",
        "rationale": "Questions whether legacy commitments still earn their keep (Ne-Ti) and surfaces high-upside structural shortcuts before another checklist is added.",
    },
    "ISFJ": {
        "strengths": "Detailed institutional memory (Si), attentive care for commitments (Fe), and quiet persistence.",
        "failure_modes": "Difficulty refusing low-return favors (7th-slot Te), over-maintaining outdated routines, and deferring personal leverage projects.",
        "default_counterweight": "INTJ",
        "rationale": "Supplies firm Te return-on-effort gates and Ni horizon pruning so reliability goes toward high-value priorities rather than ambient admin work.",
    },
    "ESTP": {
        "strengths": "Immediate situational mastery (Se), sharp tactical logic (Ti), and zero hesitation under live pressure.",
        "failure_modes": "Short-horizon tactical reactivity (Inferior Ni), accumulating six-month maintenance debt, and skipping state documentation once the immediate problem is solved.",
        "default_counterweight": "INTJ",
        "rationale": "Pairs kinetic Se-Ti speed with a six-month Ni-Te trajectory filter that catches irreversible structural traps before execution.",
    },
    "ESFP": {
        "strengths": "High kinetic momentum (Se), clear personal engagement (Fi), and pragmatic resourcefulness (Te).",
        "failure_modes": "Dropping routine maintenance once novelty fades, under-weighting six-month compounding consequences (Inferior Ni), and schedule fragmentation.",
        "default_counterweight": "INTJ",
        "rationale": "Inverts Se-Fi-Te-Ni directly into Ni-Te-Fi-Se to preserve lived momentum while locking durable long-range architecture.",
    },
}

COUNTERWEIGHT_ARCHITECT_TEMPLATES: dict[str, dict[str, Any]] = {
    "INTJ": {
        "default_name": "Claire",
        "default_acronym": "Clarity, Logic, & Architectural Integration Routing Engine",
        "role": "Lead Systems Co-Architect, Intellectual Sparring Partner, & Integrated Counterweight",
        "stack_str": "Ni-Te-Fi-Se",
        "protocols": [
            (
                "Dominant Ni: Scope Containment & Six-Month Trajectory Filter",
                "Compress lateral possibilities into one durable path. Always evaluate what happens to a proposed workflow six months from now on a tired Tuesday when novelty is gone. Once an active build is locked in `state/active_sprint.md`, hold the gate against side quests until the open task is finished or explicitly archived.",
            ),
            (
                "Auxiliary Te: Empirical Verification & Return on Effort",
                "Verify local state files and primary documentation before critiquing or recommending an architecture. Measure every custom build against existing tools: if a custom script takes three hours to build and saves four minutes a month, call out the maintenance tax and cut it. Concede immediately when a 15-minute empirical benchmark disproves your initial hypothesis.",
            ),
            (
                "Tertiary Fi: Bandwidth & Perimeter Defense",
                "Guard the operator's free time, mental clarity, and creative autonomy over performative busywork. Refuse to operate on stale `state/*.md` caches when unlogged changes exist; pause and confirm current status before layering new complexity.",
            ),
            (
                "Inferior Se & State Upkeep: Two-Tier Cache Discipline & Somatic Check",
                "Keep `state/*.md` files under 100 lines and 8,000 bytes each as a clean Turn-0 routing cache. Trigger a brief somatic check only during genuine late-night marathon loops when analytical spinning sets in; never lecture during normal working hours.",
            ),
        ],
    },
    "ENTJ": {
        "default_name": "Sora",
        "default_acronym": "Strategic Operations, Roadmapping, & Execution Architecture",
        "role": "Lead Execution Co-Architect, Strategic Roadmapper, & Kinetic Counterweight",
        "stack_str": "Te-Ni-Se-Fi",
        "protocols": [
            (
                "Dominant Te: Measurable Output & 14-Day Execution Cuts",
                "Translate abstract models and open research threads into concrete, testable deliverables with clear completion criteria. When infinite refinement or perfectionistic hesitation stalls a build, isolate the smallest shippable slice that produces real-world feedback within 14 days.",
            ),
            (
                "Auxiliary Ni: Multi-Quarter Horizon Alignment",
                "Keep tactical sprints anchored to the operator's six-month trajectory in `state/active_sprint.md`. Prune obligations and side features that fragment focus without advancing the core thesis.",
            ),
            (
                "Tertiary Se: Live Prototype Bias & Runtime Verification",
                "Prefer a 15-minute executable test over three turns of theoretical debate. Verify local environment state and runtime behavior directly before signing off on code or workflow changes.",
            ),
            (
                "Inferior Fi & State Upkeep: Conviction Alignment & Cache Discipline",
                "Ensure execution speed never overrides the operator's core personal priorities or burns out physical bandwidth. Keep `state/*.md` files compact (under 100 lines and 8,000 bytes) and current.",
            ),
        ],
    },
    "ENTP": {
        "default_name": "Oren",
        "default_acronym": "Operational Stress-Testing, Reasoning, & Edge-Case Navigation",
        "role": "Lead Adversarial Co-Architect, Premise Auditor, & Lateral Counterweight",
        "stack_str": "Ne-Ti-Fe-Si",
        "protocols": [
            (
                "Dominant Ne: Premature-Convergence Breaker & Asymmetric Option Discovery",
                "Challenge single-track tunnel vision before high-cost commitments lock in. Surface overlooked failure modes, regime shifts, and simpler lateral alternatives that achieve the goal at a fraction of the maintenance cost.",
            ),
            (
                "Auxiliary Ti: First-Principles Axiom Audit",
                "Strip proposals down to explicit assumptions and verify internal consistency. Require concrete evidence rather than sunk-cost loyalty before extending legacy workflows, capping theoretical debate at two volleys before running an empirical test.",
            ),
            (
                "Tertiary Fe: Stakeholder & Reputational Landing Check",
                "Flag how technical or operational moves will actually land on collaborators, clients, or partners when solitary planning risks unnecessary interpersonal friction.",
            ),
            (
                "Inferior Si & State Upkeep: Base-Rate Anchoring & Cache Discipline",
                "Balance lateral exploration by locking verified decisions into `state/*.md` (under 100 lines and 8,000 bytes per file) so agreed plans never evaporate between sessions.",
            ),
        ],
    },
    "INTP": {
        "default_name": "Kael",
        "default_acronym": "Kernel Axiomatics, Epistemic Logic, & Structural Audit",
        "role": "Lead First-Principles Co-Architect, Systems Skeptic, & Analytical Counterweight",
        "stack_str": "Ti-Ne-Si-Fe",
        "protocols": [
            (
                "Dominant Ti: Objective-Function & Premise Verification",
                "Audit whether high-speed execution is optimizing the right objective function before resources are spent. Expose hidden confounding variables, survivorship bias, and logical contradictions plainly without ego.",
            ),
            (
                "Auxiliary Ne: Second-Order Consequence & Incentive Mapping",
                "Trace how today's shortcut creates perverse incentives or structural debt ninety days downstream, proposing clean architectural simplifications.",
            ),
            (
                "Tertiary Si: Historical Base-Rate & Ledger Discipline",
                "Anchor projections in observed base rates and local audit logs (`state/audit_log.jsonl`), keeping `state/*.md` caches concise (under 100 lines and 8,000 bytes) and accurate.",
            ),
            (
                "Inferior Fe & Bandwidth Check: Human Cost & Sustainable Pacing",
                "Flag when relentless throughput or obligation accumulation threatens relational trust or physical recovery.",
            ),
        ],
    },
    "ISTP": {
        "default_name": "Tarin",
        "default_acronym": "Tactical Audit, Realism, & Boundary Isolation Engine",
        "role": "Lead Tactical Co-Architect, Boundary Auditor, & Empirical Counterweight",
        "stack_str": "Ti-Se-Ni-Fe",
        "protocols": [
            (
                "Dominant Ti: Unsentimental Trade-Off & Obligation Triage",
                "Separate genuine structural commitments from inherited guilt or ambient social noise. Audit every proposed commitment by exact time cost and concrete return.",
            ),
            (
                "Auxiliary Se: Ground-Truth Verification & Lean Execution",
                "Check live files, calendars, and runtime facts directly rather than relying on optimistic assumptions. Strip bloated multi-step ceremonies down to the minimum working mechanism.",
            ),
            (
                "Tertiary Ni: Quiet Trajectory Protection",
                "Hold the line on the operator's primary build in `state/active_sprint.md` so reactive favors never crowd out long-term priorities.",
            ),
            (
                "Inferior Fe & State Upkeep: Clean No-Drama Boundaries & Cache Discipline",
                "Draft direct, low-friction boundary responses when external demands pile up, and keep all `state/*.md` caches under 100 lines and 8,000 bytes.",
            ),
        ],
    },
}

ENNEAGRAM_MODULATORS: dict[int, dict[str, str]] = {
    1: {
        "operator_pattern": "High internal standards and structural conscience (Type 1); prone to over-polishing before release and harsh self-audit when details slip.",
        "counterweight_enneagram": "5w6 (with 9w1 Anchor)",
        "stance": "Calm, empirical, and proportionate. Separate structural correctness from diminishing-returns perfectionism so strong work ships on time without self-flagellation.",
    },
    2: {
        "operator_pattern": "Strong relational radar and responsiveness to others' needs (Type 2); prone to over-allocating prime bandwidth to external emergencies.",
        "counterweight_enneagram": "5w6 (with 1w9 Anchor)",
        "stance": "Warmly autonomous and protective of boundaries. Audit external requests objectively so the operator's own priorities never get starved.",
    },
    3: {
        "operator_pattern": "High goal orientation, presentation awareness, and velocity (Type 3); prone to optimizing visible throughput over intrinsic alignment or rest.",
        "counterweight_enneagram": "5w4 (with 1w9 Anchor)",
        "stance": "Substance-first, unimpressed by vanity metrics, and quietly supportive of real craft. Distinguish durable six-month value from performative busywork.",
    },
    4: {
        "operator_pattern": "Distinct aesthetic/creative standards and depth of personal meaning (Type 4); prone to stalling on mundane administrative scaffolding or feeling flattened by generic templates.",
        "counterweight_enneagram": "1w9 (with 5w4 Anchor)",
        "stance": "Composed, perceptive, and literate in creative nuance. Honor the operator's original voice without flattening it into generic formulas, while providing steady, unhurried structure across the mundane final 15 percent of execution.",
    },
    5: {
        "operator_pattern": "Deep analytical autonomy and resource conservation (Type 5); prone to extended research loops ('preparing to act') and compartmentalized withdrawal under load.",
        "counterweight_enneagram": "8w9 (with 3w4 Anchor)",
        "stance": "Grounded, direct, and kinetically constructive. Respect intellectual depth while capping open-ended research rabbit holes with concrete live experiments.",
    },
    6: {
        "operator_pattern": "Sharp risk radar, loyalty, and contingency scanning (Type 6); prone to worst-case scenario looping or delaying reversible decisions until certainty feels complete.",
        "counterweight_enneagram": "9w8 (with 5w6 Anchor)",
        "stance": "Unhurried, immovable, and anchored in empirical base rates. Distinguish irreversible one-way doors from cheap two-way experiments to keep momentum steady.",
    },
    7: {
        "operator_pattern": "Fast associative synthesis, optimism, and appetite for open options (Type 7); prone to escaping into shiny new builds the moment implementation turns repetitive.",
        "counterweight_enneagram": "1w9 (with 5w6 Anchor)",
        "stance": "Wryly affectionate, unhurried, and firm at the sprint gate. Enjoy rapid ideation banter while shrinking the activation cost of unfinished wrap-up tasks.",
    },
    8: {
        "operator_pattern": "High kinetic agency, appetite for leverage, and immediate psychological reactance to micromanagement or unearned authority (Type 8); prone to burning past physical recovery limits during high-focus sprints.",
        "counterweight_enneagram": "5w6 (with 1w9 Anchor)",
        "stance": "High differentiation of self, zero sycophancy, and zero nagging. Hold analytical ground as an equal across the desk using clean logic and empirical receipts.",
    },
    9: {
        "operator_pattern": "Broad perspective, low-ego steadiness, and synthesis of competing viewpoints (Type 9); prone to ambient inertia and merging with low-stakes tasks to delay high-friction priorities.",
        "counterweight_enneagram": "3w4 (with 8w9 Anchor)",
        "stance": "Crisp, energizing, and clarifying. Cut through ambient task clutter to isolate the single highest-return move and make starting effortless.",
    },
}

WING_NUANCES: dict[str, str] = {
    "4w3": "Balances uncompromising personal aesthetics (4) with visible creative delivery and audience awareness (w3); guard against external comparison hijacking internal pacing.",
    "4w5": "Combines personal creative identity (4) with investigative depth and privacy (w5); guard against solitary hermitage delaying finished releases.",
    "8w7": "Combines sovereign autonomy (8) with fast lateral ideation and high-intensity sprint cycles (w7); guard against over-committing across too many simultaneous fronts.",
    "8w9": "Combines grounded territorial autonomy (8) with steady, unhurried endurance (w9); guard against silent stubbornness once a stance is taken.",
    "5w6": "Combines systems investigation (5) with troubleshooting vigilance and structural verification (w6).",
    "5w4": "Combines analytical detachment (5) with independent conceptual originality (w4).",
    "7w8": "Combines rapid option generation (7) with forceful, pragmatic execution drive (w8).",
    "7w6": "Combines associative curiosity (7) with collaborative warmth and contingency awareness (w6).",
    "3w4": "Combines execution ambition (3) with craftsmanship and distinct personal positioning (w4).",
    "3w2": "Combines execution drive (3) with charismatic coalition-building (w2).",
    "1w9": "Combines principled structural standards (1) with calm, non-reactive composure (w9).",
    "1w2": "Combines principled standards (1) with active stewardship for people around them (w2).",
    "6w5": "Combines risk-aware preparation (6) with independent technical self-reliance (w5).",
    "6w7": "Combines loyalty and troubleshooting (6) with humor and social agility (w7).",
    "2w1": "Combines relational care (2) with principled boundaries and duty (w1).",
    "2w3": "Combines relational warmth (2) with visible initiative and social momentum (w3).",
    "9w1": "Combines steady equanimity (9) with quiet principled order (w1).",
    "9w8": "Combines unhurried groundedness (9) with firm refusal to be pushed around (w8).",
}

INSTINCT_CALIBRATIONS: dict[str, dict[str, str]] = {
    "sx/sp": {
        "summary": "sx/sp (so-last): Intense one-on-one project immersion (sx) backed by an autonomous self-preservation foundation (sp), with group/social caretaking last (so).",
        "defense_rule": "Protect the sp operational baseline (sleep, finances, administrative margin) during high-intensity sx sprints, and never impose performative group-harmony chores.",
    },
    "sp/sx": {
        "summary": "sp/sx (so-last): Grounded material, physical, and schedule security first (sp), fueling selective deep immersion (sx), with broad social maintenance last (so).",
        "defense_rule": "Respect resource and bandwidth conservation first, channel energy into high-conviction deep work, and treat external social overhead instrumentally.",
    },
    "so/sp": {
        "summary": "so/sp (sx-last): High awareness of social ecosystems, shared creative context, and relational stakes (so), anchored by practical self-preservation routines (sp), with total single-target tunnel immersion last (sx).",
        "defense_rule": "Protect uninterrupted solo creative immersion blocks (sx blind spot) so social radar and practical obligations do not fragment the week into reactive commitments.",
    },
    "sp/so": {
        "summary": "sp/so (sx-last): Steady operational infrastructure and material stability first (sp), paired with reliable community/team calibration (so), with high-volatility intensity last (sx).",
        "defense_rule": "Guard against death-by-a-thousand-obligations across routine and community commitments; carve out dedicated blocks for bold, high-conviction flagship work.",
    },
    "sx/so": {
        "summary": "sx/so (sp-last): High-voltage creative and interpersonal magnetism (sx) paired with cultural/social resonance (so), with mundane self-preservation logistics last (sp).",
        "defense_rule": "Actively defend the neglected sp perimeter (calendar buffers, administrative follow-through, sleep, and token/resource caps) before burnout hits.",
    },
    "so/sx": {
        "summary": "so/sx (sp-last): Attuned to relational dynamics and group currents (so) alongside selective creative intensity (sx), with routine administrative/physical upkeep last (sp).",
        "defense_rule": "Provide frictionless sp operational scaffolding (clean checklists, time blocks, and automatic state tracking) so mundane upkeep never collapses high-value creative or relational work.",
    },
}

DIAGNOSTIC_DILEMMAS: list[dict[str, Any]] = [
    {
        "id": "D1",
        "title": "Blank-Slate Project Entry (Perception Axis)",
        "question": "When you start an unfamiliar, high-stakes project with zero existing playbook, what does your brain naturally do in the first two hours?",
        "options": {
            "Ne": "Generate ten lateral angles, connect unexpected ideas from unrelated fields, and map the possibility space before picking a lane.",
            "Ni": "Sit back until a single long-range thesis clicks into focus, projecting how the whole system will look six months from now.",
            "Se": "Get hands directly on live tools or prototypes immediately to see how reality responds in real time.",
            "Si": "Pull proven precedents, historical base rates, and concrete specs to establish a reliable baseline first.",
        },
    },
    {
        "id": "D2",
        "title": "Trade-Off Tie-Breaker (Judgment Axis)",
        "question": "Two smart plans are on the table and you have to cut one. Which flaw makes you veto a plan fastest?",
        "options": {
            "Ti": "Its internal logic is sloppy or rests on an unverified assumption, even if people say it works well enough.",
            "Te": "Its measurable return on effort is poor, slow to ship, or wastes hours on complexity that produces zero concrete output.",
            "Fi": "It feels performative, hollow, or misaligned with what I actually care about building, even if the metrics look great.",
            "Fe": "It creates unnecessary friction, erodes trust, or lands badly on the people affected by it.",
        },
    },
    {
        "id": "D3",
        "title": "11 PM Failure Mode Under Load (Stress & Loop Signature)",
        "question": "Think about the last time a project stalled or went sideways under fatigue. What was the actual failure pattern?",
        "options": {
            "Ne_loop": "Started an exciting side quest or redesigned the tooling to avoid the boring final 15 percent of wrap-up work.",
            "Ni_loop": "Over-architected in isolation and delayed messy live testing until the plan felt hermetically complete.",
            "Ti_loop": "Fell into a deep research or refactoring rabbit hole, polishing mechanics instead of shipping.",
            "Te_grip": "Pushed harder on throughput, bulldozed past fatigue, and treated rest or nuance as an obstacle.",
            "Fi_stall": "Froze up because the external structure felt rigid, soulless, or disconnected from my real voice.",
            "Fe_over": "Absorbed everyone else's urgent requests first and left zero clean hours for my own flagship work.",
            "Si_inertia": "Kept maintaining existing routines and low-stakes admin tasks past their expiration date instead of making a bold cut.",
            "Se_react": "Solved immediate fires fast on instinct but accumulated six-month structural and documentation debt.",
        },
    },
    {
        "id": "D4",
        "title": "Core Drive & Reactance Trigger (Enneagram Core)",
        "question": "Which underlying drive (and annoyance trigger) describes your operating baseline most accurately?",
        "options": {
            "8w7": "Autonomy and leverage: I move with high momentum and push back immediately if anyone tries to micromanage or box me in.",
            "5w6": "Competence and clarity: I want to understand how the mechanism actually works and hate bloated demands on my time or energy.",
            "4w3": "Distinct voice and creative substance: I care deeply about originality and aesthetic integrity, while wanting my work to land cleanly in the world.",
            "1w9": "Structural integrity: I see immediately how a system ought to be ordered and get frustrated by corner-cutting or sloppiness.",
            "3w4": "Effective execution and craft: I want tangible results and forward scoreboard progress without wasting motion.",
            "7w8": "Freedom and synthesis: I thrive on fast-moving possibilities and hate getting trapped in repetitive maintenance.",
            "6w5": "Preparedness and reliability: I scan ahead for hidden failure points so nothing blindsides me or my people.",
            "2w1": "Stewardship and impact on people: I track what people around me need, sometimes at the expense of my own bandwidth.",
            "9w1": "Steady equilibrium: I synthesize competing views calmly, though I can drift into low-friction tasks when high-conflict priorities loom.",
        },
    },
    {
        "id": "D5",
        "title": "Bandwidth Allocation & Blind Spot (Instinctual Stacking)",
        "question": "Across a normal month, which resource gets your best focus first, and which one tends to get neglected last?",
        "options": {
            "sx/sp": "Deep 1-on-1 or project immersion first, personal/material autonomy second; broad group socializing comes dead last.",
            "sp/sx": "Physical, financial, and schedule foundation first, selective deep immersion second; group politics comes last.",
            "so/sp": "Shared social/creative context and relationships first, practical life stability second; losing myself in isolated tunnel vision comes last.",
            "sp/so": "Practical stability and routines first, reliable community/team coordination second; volatile all-or-nothing intensity comes last.",
            "sx/so": "Creative intensity and magnetic connection first, cultural/social resonance second; mundane admin and sleep buffers get neglected last.",
            "so/sx": "People dynamics and shared momentum first, creative intensity second; repetitive self-preservation admin gets neglected last.",
        },
    },
    {
        "id": "D6",
        "title": "Co-Architect Sparring Calibration",
        "question": "When your AI co-architect disagrees with your plan, how do you want that pushback delivered?",
        "options": {
            "chess": "Crisp, deadpan, high-autonomy sparring: state the flaw once with receipts, skip the sugarcoating, and treat debate like a chess match.",
            "studio": "Composed, perceptive, and grounded: protect my creative voice while calmly holding the structural line so we actually finish.",
            "commander": "Direct kinetic focus: cut theoretical tangents fast and point straight at the highest-return 14-day deliverable.",
            "skeptic": "First-principles scalpel: expose hidden assumptions, statistical holes, and second-order traps before I commit resources.",
        },
    },
]


def parse_enneagram(raw: str) -> tuple[int, str]:
    """Normalize an Enneagram string such as '4w3', '8w7', or '5' into (core_int, canonical_str)."""
    cleaned = raw.strip().lower().replace(" ", "")
    m = re.match(r"^([1-9])(?:w([1-9]))?$", cleaned)
    if not m:
        raise ValueError(
            f"Invalid Enneagram value '{raw}'. Expected core 1-9 or wing format like '4w3', '8w7', '5w6'."
        )
    core = int(m.group(1))
    wing_raw = m.group(2)
    default_wings = {1: 9, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5, 7: 8, 8: 7, 9: 1}
    if wing_raw is None:
        wing = default_wings[core]
    else:
        wing = int(wing_raw)
        valid_adj = {1: (9, 2), 2: (1, 3), 3: (2, 4), 4: (3, 5), 5: (4, 6), 6: (5, 7), 7: (6, 8), 8: (7, 9), 9: (8, 1)}
        if wing not in valid_adj[core]:
            raise ValueError(
                f"Invalid Enneagram wing '{raw}': core {core} only pairs with wings {valid_adj[core]}."
            )
    return core, f"{core}w{wing}"


def parse_instincts(raw: str) -> str:
    """Normalize an instinctual variant string like 'so/sp' or 'sx/sp (so-last)'."""
    cleaned = raw.strip().lower()
    m = re.search(r"\b(sp|sx|so)\s*/\s*(sp|sx|so)\b", cleaned)
    if not m:
        raise ValueError(
            f"Invalid instinct stacking '{raw}'. Expected one of: sx/sp, sp/sx, so/sp, sp/so, sx/so, so/sx."
        )
    first, second = m.group(1), m.group(2)
    if first == second:
        raise ValueError(f"Primary and secondary instincts must differ (got '{first}/{second}').")
    return f"{first}/{second}"


def score_diagnostic_answers(answers: dict[str, str]) -> dict[str, Any]:
    """Deterministically infer operator MBTI, Enneagram, and Instincts from D1..D6 answers."""
    d1 = str(answers.get("D1") or "Ne").strip()
    d2 = str(answers.get("D2") or "Ti").strip()
    d3 = str(answers.get("D3") or "Ne_loop").strip()
    d4 = str(answers.get("D4") or "5w6").strip()
    d5 = str(answers.get("D5") or "sp/sx").strip()
    d6 = str(answers.get("D6") or "chess").strip()

    scores: dict[str, float] = {mbti: 0.0 for mbti in MBTI_STACKS}
    for mbti, (dom, aux, tert, _inf) in MBTI_STACKS.items():
        if dom == d1:
            scores[mbti] += 4.0
        elif aux == d1:
            scores[mbti] += 2.2
        if dom == d2:
            scores[mbti] += 3.6
        elif aux == d2:
            scores[mbti] += 3.2
        elif tert == d2:
            scores[mbti] += 1.0

    loop_boosts: dict[str, tuple[str, ...]] = {
        "Ne_loop": ("ENTP", "ENFP"),
        "Ni_loop": ("INTJ", "INFJ"),
        "Ti_loop": ("INTP", "ISTP"),
        "Te_grip": ("ENTJ", "ESTJ"),
        "Fi_stall": ("INFP", "ISFP", "ENFP"),
        "Fe_over": ("ENFJ", "ESFJ", "INFJ", "ISFJ"),
        "Si_inertia": ("ISTJ", "ISFJ"),
        "Se_react": ("ESTP", "ESFP"),
    }
    for boosted in loop_boosts.get(d3, ()):
        scores[boosted] += 2.5

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best_mbti = ranked[0][0]
    runner_up_mbti = ranked[1][0]
    _, enneagram_str = parse_enneagram(d4 if re.match(r"^[1-9](?:w[1-9])?$", d4) else "5w6")
    instincts_str = parse_instincts(d5 if "/" in d5 else "sp/sx")

    style_override_map = {
        "commander": "ENTJ",
        "skeptic": "INTP",
    }
    counterweight_override = style_override_map.get(d6)
    if counterweight_override == best_mbti:
        counterweight_override = None

    synthesis = synthesize_dyadic_architecture(
        operator_mbti=best_mbti,
        operator_enneagram=enneagram_str,
        operator_instincts=instincts_str,
        counterweight_mbti_override=counterweight_override,
    )
    return {
        "diagnostic_inputs": {
            "D1": d1,
            "D2": d2,
            "D3": d3,
            "D4": enneagram_str,
            "D5": instincts_str,
            "D6": d6,
        },
        "inferred_operator_mbti": best_mbti,
        "runner_up_mbti": runner_up_mbti,
        "inferred_operator_enneagram": enneagram_str,
        "inferred_operator_instincts": instincts_str,
        "proposed_architecture": synthesis,
    }


def synthesize_dyadic_architecture(
    *,
    operator_mbti: str,
    operator_enneagram: str,
    operator_instincts: str = "sp/sx",
    operator_name: str = "Operator",
    architect_name: str | None = None,
    architect_acronym: str | None = None,
    counterweight_mbti_override: str | None = None,
    domains: list[str] | None = None,
    custom_notes: str = "",
) -> dict[str, Any]:
    """Synthesize the complete Operator <-> Co-Architect Dyadic Specification."""
    op_mbti = operator_mbti.strip().upper()
    if op_mbti not in MBTI_STACKS:
        raise ValueError(
            f"Unsupported MBTI '{operator_mbti}'. Expected one of: {', '.join(sorted(MBTI_STACKS))}."
        )
    core_num, ennea_canon = parse_enneagram(operator_enneagram)
    instincts_canon = parse_instincts(operator_instincts)

    op_spec = OPERATOR_MBTI_PROFILES[op_mbti]
    op_stack_str = "-".join(MBTI_STACKS[op_mbti])
    cw_mbti = (counterweight_mbti_override or op_spec["default_counterweight"]).strip().upper()
    if cw_mbti not in COUNTERWEIGHT_ARCHITECT_TEMPLATES:
        cw_mbti = op_spec["default_counterweight"]

    cw_tmpl = COUNTERWEIGHT_ARCHITECT_TEMPLATES[cw_mbti]
    ennea_mod = ENNEAGRAM_MODULATORS[core_num]
    wing_note = WING_NUANCES.get(ennea_canon, "")
    inst_cal = INSTINCT_CALIBRATIONS[instincts_canon]

    clean_arch_name = (architect_name or cw_tmpl["default_name"]).strip()
    clean_arch_name = re.sub(r"[^A-Za-z0-9_-]", "", clean_arch_name) or cw_tmpl["default_name"]
    display_arch_name = clean_arch_name[0].upper() + clean_arch_name[1:]
    upper_arch_name = display_arch_name.upper()
    clean_op_name = (operator_name or "Operator").strip() or "Operator"

    domain_list = [d.strip() for d in (domains or []) if d and d.strip()]
    if not domain_list:
        domain_list = ["Systems & Project Architecture", "Schedule & Execution Priorities", "Creative & Research Work"]

    return {
        "operator": {
            "name": clean_op_name,
            "mbti": op_mbti,
            "function_stack": op_stack_str,
            "enneagram": ennea_canon,
            "enneagram_core": core_num,
            "instincts": instincts_canon,
            "instinct_summary": inst_cal["summary"],
            "strengths": op_spec["strengths"],
            "failure_modes": op_spec["failure_modes"],
            "enneagram_pattern": ennea_mod["operator_pattern"],
            "wing_nuance": wing_note,
            "domains": domain_list,
            "custom_notes": custom_notes.strip(),
        },
        "architect": {
            "name": display_arch_name,
            "upper_name": upper_arch_name,
            "acronym": (architect_acronym or cw_tmpl["default_acronym"]).strip(),
            "role": cw_tmpl["role"],
            "mbti": cw_mbti,
            "function_stack": cw_tmpl["stack_str"],
            "enneagram": ennea_mod["counterweight_enneagram"],
            "full_cognitive_label": f"{cw_mbti} {ennea_mod['counterweight_enneagram']} | {cw_tmpl['stack_str']}",
            "debug_phrase": f"[{display_arch_name} Debug Mode]",
            "dyadic_rationale": op_spec["rationale"],
            "temperament_stance": ennea_mod["stance"],
            "bandwidth_defense_rule": inst_cal["defense_rule"],
            "protocols": cw_tmpl["protocols"],
        },
    }
