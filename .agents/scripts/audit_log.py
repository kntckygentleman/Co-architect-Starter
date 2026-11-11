#!/usr/bin/env python3
"""Cross-Platform SHA-256 Provenance Verifier, Epistemic Auditor, ADR Recorder, & Token Telemetry CLI.

Subcommands:
- verify: Validate the canonical JSON SHA-256 hash chain across rotated .bak segments and state/audit_log.jsonl.
- summary: Aggregate tool executions, mutations, blocks, and subagent runs over a rolling window.
- query: Filter and inspect signal entries from state/audit_log.jsonl.
- changelog: Render a grouped Keep-a-Changelog view from CODE_SYSTEM and ADR_DECISION events.
- record-adr: Validate against human-voice.md, append ADR-XXXX to state/archive_decisions.md, and log provenance.
- epistemic: Run congruence, state-cap, security-incident, and parity checks (--check, --clear-taint, --ack-incidents).
- tokens: Measure Turn-0 prompt/rule/state token footprint and 7-day subagent model tiering usage.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import glob
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core_hooks import (  # noqa: E402
    GENESIS_HASH,
    REQUIRED_PERSONA_MARKERS,
    VALID_SEAT_IDENTITY_RE,
    append_locked_audit_entry,
    audit_state_files,
    compute_entry_hash,
    exclusive_file_lock,
    file_sha256_and_size,
    git_head_short,
    lint_markdown_slop,
    lint_security_payload,
    now_local,
    resolve_workspace_root,
)
from workspace_hooks import load_workspace_config  # noqa: E402

WORKSPACE_ROOT = resolve_workspace_root(__file__)


def _ordered_segments(log_path: str) -> list[str]:
    segs = sorted(glob.glob(f"{log_path}.*.bak"))
    if os.path.isfile(log_path):
        segs.append(log_path)
    return segs


def read_all_entries(log_path: str) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    for seg in _ordered_segments(log_path):
        seg_name = os.path.basename(seg)
        try:
            with open(seg, "r", encoding="utf-8") as f:
                for idx, ln in enumerate(f, start=1):
                    s = ln.strip()
                    if not s:
                        continue
                    try:
                        obj = json.loads(s)
                        if isinstance(obj, dict):
                            entries.append(obj)
                        else:
                            errors.append(f"{seg_name}:{idx} non-object JSON")
                    except json.JSONDecodeError as exc:
                        errors.append(f"{seg_name}:{idx} JSON parse error: {exc}")
        except OSError as exc:
            errors.append(f"{seg_name}: read error: {exc}")
    return entries, errors


def cmd_verify(_args: argparse.Namespace) -> int:
    log_path = os.path.join(WORKSPACE_ROOT, "state", "audit_log.jsonl")
    entries, errors = read_all_entries(log_path)
    if errors:
        print(json.dumps({"status": "FAIL", "parse_errors": errors}, indent=2))
        return 1
    expected_prev = GENESIS_HASH
    for idx, entry in enumerate(entries, start=1):
        actual_prev = entry.get("prev_hash")
        recorded_hash = entry.get("entry_hash")
        core = {k: v for k, v in entry.items() if k != "entry_hash"}
        recomputed = compute_entry_hash(core)
        if actual_prev != expected_prev:
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "entry_index": idx,
                        "reason": "prev_hash chain break",
                        "expected_prev": expected_prev[:16],
                        "actual_prev": str(actual_prev)[:16],
                    },
                    indent=2,
                )
            )
            return 1
        if recorded_hash != recomputed:
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "entry_index": idx,
                        "reason": "entry_hash tamper/mismatch",
                        "recorded": str(recorded_hash)[:16],
                        "recomputed": recomputed[:16],
                    },
                    indent=2,
                )
            )
            return 1
        expected_prev = recorded_hash
    print(
        json.dumps(
            {
                "status": "OK",
                "verified_entries": len(entries),
                "head_hash": expected_prev[:16] if entries else "GENESIS",
            },
            indent=2,
        )
    )
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    cfg = load_workspace_config(WORKSPACE_ROOT)
    cutoff = (now_local(cfg.get("timezone")) - timedelta(days=args.days)).isoformat()
    log_path = os.path.join(WORKSPACE_ROOT, "state", "audit_log.jsonl")
    entries, _ = read_all_entries(log_path)
    window = [e for e in entries if str(e.get("ts") or "") >= cutoff]
    cats = Counter(str(e.get("category") or "UNKNOWN") for e in window)
    mutated_files = sorted(
        {
            str(e.get("target") or "")
            for e in window
            if e.get("mutated") is True and e.get("category") in ("CODE_SYSTEM", "STATE_CACHE")
        }
    )
    print(
        json.dumps(
            {
                "window_days": args.days,
                "total_events": len(window),
                "by_category": dict(cats),
                "mutated_targets": mutated_files,
            },
            indent=2,
        )
    )
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    log_path = os.path.join(WORKSPACE_ROOT, "state", "audit_log.jsonl")
    entries, _ = read_all_entries(log_path)
    filtered: list[dict[str, Any]] = []
    for e in entries:
        cat = str(e.get("category") or "")
        if not args.include_reads and cat in ("READ_QUERY", "ARTIFACT_STAGE") and not e.get("mutated"):
            continue
        if args.category and cat.upper() != args.category.upper():
            continue
        filtered.append(e)
    for rec in filtered[-args.limit :]:
        print(json.dumps(rec, ensure_ascii=False))
    return 0


def cmd_changelog(args: argparse.Namespace) -> int:
    log_path = os.path.join(WORKSPACE_ROOT, "state", "audit_log.jsonl")
    entries, _ = read_all_entries(log_path)
    by_day: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        cat = str(e.get("category") or "")
        if cat not in ("CODE_SYSTEM", "ADR_DECISION") and not e.get("mutated"):
            continue
        day = str(e.get("ts") or "")[:10] or "unknown"
        tgt = os.path.basename(str(e.get("target") or ""))
        summ = str(e.get("summary") or "")
        line = f"- `{tgt}`: {summ}"
        if line not in by_day[day]:
            by_day[day].append(line)
    days_sorted = sorted(by_day.keys(), reverse=True)[: args.days]
    if not days_sorted:
        print("# Workspace Provenance Changelog\n\nNo recorded mutations yet.")
        return 0
    lines = ["# Workspace Provenance Changelog", ""]
    for d in days_sorted:
        lines.append(f"## {d}")
        lines.extend(by_day[d])
        lines.append("")
    print("\n".join(lines).rstrip())
    return 0


def cmd_record_adr(args: argparse.Namespace) -> int:
    cfg = load_workspace_config(WORKSPACE_ROOT)
    tz_name = cfg.get("timezone")
    today_iso = now_local(tz_name).date().isoformat()
    adr_path = os.path.join(WORKSPACE_ROOT, "state", "archive_decisions.md")
    combined_text = f"{args.title}\n{args.context}\n{args.decision}\n{args.consequences}"
    sec_err = lint_security_payload("archive_decisions.md", combined_text, check_stored_injection=True)
    if sec_err:
        sys.stderr.write(f"{sec_err}\n")
        return 1
    slop_err = lint_markdown_slop("archive_decisions.md", combined_text)
    if slop_err:
        sys.stderr.write(f"{slop_err}\n")
        return 1

    os.makedirs(os.path.dirname(adr_path), exist_ok=True)
    with open(adr_path, "a+", encoding="utf-8") as af:
        with exclusive_file_lock(af):
            af.seek(0)
            existing = af.read()
            nums = [int(m) for m in re.findall(r"\bADR-(\d{4})\b", existing)]
            next_num = (max(nums) + 1) if nums else 1
            adr_id = f"ADR-{next_num:04d}"
            sha_before, _ = file_sha256_and_size(adr_path)
            if not existing.strip():
                header = (
                    f"# ARCHITECTURAL DECISION RECORDS (COMPACT INDEX)\n"
                    f"**Last Updated:** {today_iso} | **Line Cap:** 150\n\n"
                )
                existing = header
            else:
                existing = re.sub(
                    r"(\*\*Last Updated:\*\*\s*)\d{4}-\d{2}-\d{2}",
                    rf"\g<1>{today_iso}",
                    existing,
                    count=1,
                )
            block = (
                f"- **{adr_id} ({today_iso}) [{args.status.upper()}]: {args.title.strip()}**\n"
                f"  - *Context:* {args.context.strip()}\n"
                f"  - *Decision:* {args.decision.strip()}\n"
                f"  - *Consequences:* {args.consequences.strip()}\n"
            )
            new_full = existing.rstrip() + "\n" + block
            af.seek(0)
            af.truncate()
            af.write(new_full)
            af.flush()

    sha_after, bytes_after = file_sha256_and_size(adr_path)
    append_locked_audit_entry(
        os.path.join(WORKSPACE_ROOT, "state", "audit_log.jsonl"),
        {
            "ts": now_local(tz_name).isoformat(timespec="seconds"),
            "conv_id": "cli",
            "step_idx": None,
            "category": "ADR_DECISION",
            "tool": "audit_log.py:record-adr",
            "target": adr_id,
            "summary": f"{adr_id}: {args.title.strip()[:140]}",
            "status": "OK",
            "sha256_before": sha_before[:16] if sha_before else None,
            "sha256_after": sha_after[:16] if sha_after else None,
            "bytes_after": bytes_after,
            "mutated": True,
            "git_head": git_head_short(WORKSPACE_ROOT),
        },
        tz_name=tz_name,
    )
    print(json.dumps({"status": "OK", "adr_id": adr_id, "path": adr_path}, indent=2))
    return 0


def cmd_epistemic(args: argparse.Namespace) -> int:
    cfg = load_workspace_config(WORKSPACE_ROOT)
    tz_name = cfg.get("timezone")
    manifest_path = os.path.join(WORKSPACE_ROOT, "state", "epistemic_manifest.json")

    if args.clear_taint or args.ack_incidents:
        if os.path.isfile(manifest_path):
            with open(manifest_path, "a+", encoding="utf-8") as mf:
                with exclusive_file_lock(mf):
                    mf.seek(0)
                    raw = mf.read().strip()
                    data = json.loads(raw) if raw else {}
                    if args.clear_taint:
                        for c_rec in (data.get("conv_reads") or {}).values():
                            if isinstance(c_rec, dict):
                                c_rec["taint_sources"] = []
                    if args.ack_incidents:
                        for inc in data.get("security_incidents") or []:
                            if isinstance(inc, dict):
                                inc["acknowledged"] = True
                    mf.seek(0)
                    mf.truncate()
                    mf.write(json.dumps(data, indent=2) + "\n")
                    mf.flush()
        print(json.dumps({"status": "OK", "cleared_taint": args.clear_taint, "acked_incidents": args.ack_incidents}))
        return 0

    issues: list[str] = []
    raw_specs = cfg.get("state_files_to_audit") or []
    specs = [
        (
            str(it["label"]),
            os.path.join(WORKSPACE_ROOT, "state", str(it["label"])),
            int(it.get("max_lines") or 100),
            int(it.get("max_bytes") or 8000),
            int(it["max_stale_days"]) if it.get("max_stale_days") is not None else None,
        )
        for it in raw_specs
        if isinstance(it, dict) and it.get("label")
    ]
    audit_res = audit_state_files(specs, workspace_root=WORKSPACE_ROOT, tz_name=tz_name)
    if audit_res.get("additionalContext"):
        issues.append(str(audit_res["additionalContext"]))

    sys_p = os.path.join(WORKSPACE_ROOT, "SYSTEM_PROMPT.md")
    if os.path.isfile(sys_p):
        txt = Path(sys_p).read_text(encoding="utf-8", errors="replace")
        for marker in REQUIRED_PERSONA_MARKERS:
            if marker not in txt:
                issues.append(f"SYSTEM_PROMPT.md missing required persona marker: {marker}")

    for spec_rel in (
        ".agents/skills/council/references/personas.md",
        ".agents/skills/iterate/references/critic_panels.md",
    ):
        sp = os.path.join(WORKSPACE_ROOT, *spec_rel.split("/"))
        if os.path.isfile(sp):
            for ln in Path(sp).read_text(encoding="utf-8", errors="replace").splitlines():
                if ln.startswith("# COUNCIL SEAT IDENTITY:") and not VALID_SEAT_IDENTITY_RE.match(ln):
                    issues.append(f"{spec_rel} invalid seat header: {ln}")

    status = "PASS" if not issues else "FAIL"
    print(json.dumps({"status": status, "issues": issues}, indent=2))
    return 0 if status == "PASS" else 1


def cmd_tokens(_args: argparse.Namespace) -> int:
    cfg = load_workspace_config(WORKSPACE_ROOT)
    files_to_measure = [
        "SYSTEM_PROMPT.md",
        ".agents/rules/human-voice.md",
        ".agents/rules/state-hydration.md",
        "state/operator_profile.md",
        "state/routing_matrix.md",
        "state/active_sprint.md",
    ]
    breakdown: dict[str, dict[str, int]] = {}
    total_chars = 0
    for rel in files_to_measure:
        p = os.path.join(WORKSPACE_ROOT, *rel.split("/"))
        if os.path.isfile(p):
            txt = Path(p).read_text(encoding="utf-8", errors="replace")
            chars = len(txt)
            est_tokens = max(1, round(chars / 4))
            breakdown[rel] = {"chars": chars, "est_tokens": est_tokens}
            total_chars += chars

    log_path = os.path.join(WORKSPACE_ROOT, "state", "audit_log.jsonl")
    entries, _ = read_all_entries(log_path)
    cutoff_7d = (now_local(cfg.get("timezone")) - timedelta(days=7)).isoformat()
    sub_models: Counter[str] = Counter()
    for e in entries:
        if e.get("category") == "SUBAGENT" and str(e.get("ts") or "") >= cutoff_7d:
            m = re.search(r"\[model=([^\]]+)\]", str(e.get("summary") or ""))
            sub_models[m.group(1) if m else "unknown"] += 1

    print(
        json.dumps(
            {
                "architect_name": cfg.get("architect_name", "Bootstrap"),
                "turn_0_total_chars": total_chars,
                "turn_0_est_tokens": round(total_chars / 4),
                "files": breakdown,
                "subagent_dispatches_7d": dict(sub_models),
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Co-Architect Provenance, ADR, Epistemic, & Token CLI")
    sub = p.add_subparsers(dest="subcmd", required=True)

    sub.add_parser("verify", help="Verify SHA-256 hash chain in state/audit_log.jsonl")

    s_sum = sub.add_parser("summary", help="Summarize recent audit activity")
    s_sum.add_argument("--days", type=int, default=14)

    s_qry = sub.add_parser("query", help="Query signal entries from audit_log.jsonl")
    s_qry.add_argument("--limit", type=int, default=25)
    s_qry.add_argument("--category", default="")
    s_qry.add_argument("--include-reads", action="store_true")

    s_chg = sub.add_parser("changelog", help="Render Keep-a-Changelog view from provenance events")
    s_chg.add_argument("--days", type=int, default=14)

    s_adr = sub.add_parser("record-adr", help="Record an Architectural Decision Record")
    s_adr.add_argument("--title", required=True)
    s_adr.add_argument("--context", required=True)
    s_adr.add_argument("--decision", required=True)
    s_adr.add_argument("--consequences", required=True)
    s_adr.add_argument("--status", default="ACCEPTED")

    s_epi = sub.add_parser("epistemic", help="Check state caps, persona congruence, and security manifest")
    s_epi.add_argument("--check", action="store_true")
    s_epi.add_argument("--clear-taint", action="store_true")
    s_epi.add_argument("--ack-incidents", action="store_true")

    sub.add_parser("tokens", help="Measure Turn-0 token budget and 7-day subagent tier telemetry")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "verify": cmd_verify,
        "summary": cmd_summary,
        "query": cmd_query,
        "changelog": cmd_changelog,
        "record-adr": cmd_record_adr,
        "epistemic": cmd_epistemic,
        "tokens": cmd_tokens,
    }
    return dispatch[args.subcmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
