#!/usr/bin/env python3
"""Cross-Platform Self-Assembling Co-Architect Bootstrap CLI (`bootstrap.py`).

Zero external dependencies (Python 3.9+ stdlib).
Detects host OS/Python/timezone, scores the optional 6-dilemma cognitive interview,
synthesizes the Operator <-> Co-Architect dyadic counterweight, writes cross-platform
Antigravity hooks and L1 state caches, and verifies the live harness end-to-end.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

STARTER_ROOT = Path(__file__).resolve().parent
if str(STARTER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_ROOT))
SCRIPTS_DIR = STARTER_ROOT / ".agents" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from core_hooks import (  # noqa: E402
    append_locked_audit_entry,
    file_sha256_and_size,
    git_head_short,
    lint_markdown_slop,
    lint_security_payload,
    now_local,
)
from engine.cognitive_matrix import (  # noqa: E402
    DIAGNOSTIC_DILEMMAS,
    score_diagnostic_answers,
    synthesize_dyadic_architecture,
)
from engine.host_probe import detect_host_environment  # noqa: E402
from engine.renderer import (  # noqa: E402
    render_active_sprint_md,
    render_archive_decisions_md,
    render_hooks_json,
    render_operator_profile_md,
    render_routing_matrix_md,
    render_state_hydration_rule,
    render_system_prompt,
    render_workspace_config_json,
)


def _copy_agents_tree_if_external(target_dir: Path) -> None:
    src_agents = STARTER_ROOT / ".agents"
    dst_agents = target_dir / ".agents"
    if src_agents.resolve() == dst_agents.resolve():
        return
    for sub_rel in ("rules/human-voice.md", "scripts", "skills"):
        s_path = src_agents / sub_rel
        d_path = dst_agents / sub_rel
        if s_path.is_file():
            d_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s_path, d_path)
        elif s_path.is_dir():
            if d_path.exists():
                shutil.rmtree(d_path)
            shutil.copytree(
                s_path,
                d_path,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "Thumbs.db"),
            )


def _ensure_posix_exec_bits(target_dir: Path) -> None:
    if os.name == "nt":
        return
    for py_file in (target_dir / ".agents").rglob("*.py"):
        try:
            mode = py_file.stat().st_mode
            py_file.chmod(mode | 0o111)
        except OSError:
            pass


def _run_hook_probe(
    py_exe: str,
    hooks_script: Path,
    event: str,
    payload: dict[str, Any],
    ws_root: Path,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["COARCHITECT_WORKSPACE_ROOT"] = str(ws_root)
    proc = subprocess.run(
        [py_exe, str(hooks_script), event],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=10,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Hook {event} exited with {proc.returncode}: {proc.stderr.strip()}")
    out_raw = proc.stdout.strip()
    return json.loads(out_raw) if out_raw else {}


def verify_installation(target_dir: Path) -> dict[str, Any]:
    """Run live smoke checks on SessionStart, PreToolUse locks/anti-slop, and SHA-256 audit chain."""
    ws_root = target_dir.resolve()
    hooks_script = ws_root / ".agents" / "scripts" / "workspace_hooks.py"
    audit_script = ws_root / ".agents" / "scripts" / "audit_log.py"
    hooks_json_path = ws_root / ".agents" / "hooks.json"
    cfg_path = ws_root / "state" / "workspace_config.json"

    checks: dict[str, Any] = {}
    if not hooks_json_path.is_file() or not cfg_path.is_file():
        return {"status": "FAIL", "reason": "Missing .agents/hooks.json or state/workspace_config.json"}

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    py_exe = sys.executable or "python3"

    sess_out = _run_hook_probe(py_exe, hooks_script, "SessionStart", {}, ws_root)
    checks["session_start_clean"] = "additionalContext" not in sess_out
    if not checks["session_start_clean"]:
        checks["session_start_alert"] = sess_out.get("additionalContext")

    lock_probe = _run_hook_probe(
        py_exe,
        hooks_script,
        "PreToolUse",
        {
            "conversationId": "bootstrap-verify",
            "lastUserInput": "Please rewrite GEMINI.md for me",
            "toolCall": {
                "name": "write_file",
                "args": {"Path": str(ws_root / "GEMINI.md"), "Content": "# Overwrite"},
            },
        },
        ws_root,
    )
    checks["core_lock_enforced"] = lock_probe.get("decision") == "deny"

    slop_probe = _run_hook_probe(
        py_exe,
        hooks_script,
        "PreToolUse",
        {
            "conversationId": "bootstrap-verify",
            "lastUserInput": "Add sprint note",
            "toolCall": {
                "name": "write_file",
                "args": {
                    "Path": str(ws_root / "state" / "active_sprint.md"),
                    "Content": "Let us delve into this \u2014 right now.",
                },
            },
        },
        ws_root,
    )
    checks["anti_slop_enforced"] = slop_probe.get("decision") == "deny"

    env = dict(os.environ)
    env["COARCHITECT_WORKSPACE_ROOT"] = str(ws_root)
    ver_proc = subprocess.run(
        [py_exe, str(audit_script), "verify"],
        text=True,
        capture_output=True,
        timeout=10,
        env=env,
        check=False,
    )
    ver_json = json.loads(ver_proc.stdout.strip()) if ver_proc.stdout.strip() else {}
    checks["audit_chain_verified"] = ver_proc.returncode == 0 and ver_json.get("status") == "OK"

    epi_proc = subprocess.run(
        [py_exe, str(audit_script), "epistemic", "--check"],
        text=True,
        capture_output=True,
        timeout=10,
        env=env,
        check=False,
    )
    epi_json = json.loads(epi_proc.stdout.strip()) if epi_proc.stdout.strip() else {}
    checks["epistemic_congruence"] = epi_proc.returncode == 0 and epi_json.get("status") == "PASS"

    tok_proc = subprocess.run(
        [py_exe, str(audit_script), "tokens"],
        text=True,
        capture_output=True,
        timeout=10,
        env=env,
        check=False,
    )
    tok_json = json.loads(tok_proc.stdout.strip()) if tok_proc.stdout.strip() else {}

    all_ok = all(
        bool(checks.get(k))
        for k in (
            "session_start_clean",
            "core_lock_enforced",
            "anti_slop_enforced",
            "audit_chain_verified",
            "epistemic_congruence",
        )
    )
    return {
        "status": "VERIFIED" if all_ok else "FAIL",
        "architect_name": cfg.get("architect_name"),
        "debug_phrase": cfg.get("debug_phrase"),
        "workspace_root": str(ws_root),
        "turn_0_est_tokens": tok_json.get("turn_0_est_tokens"),
        "checks": checks,
    }


def cmd_detect(args: argparse.Namespace) -> int:
    target = Path(args.target_dir).resolve()
    info = detect_host_environment(target)
    print(json.dumps(info, indent=2))
    return 0


def cmd_grill(args: argparse.Namespace) -> int:
    if args.format == "text":
        blocks: list[str] = []
        for d in DIAGNOSTIC_DILEMMAS:
            opts = "\n".join(f"  - [{k}] {v}" for k, v in d["options"].items())
            blocks.append(f"### {d['id']}: {d['title']}\n{d['question']}\n{opts}")
        print("\n\n".join(blocks))
    else:
        print(json.dumps({"dilemmas": DIAGNOSTIC_DILEMMAS}, indent=2))
    return 0


def cmd_score_quiz(args: argparse.Namespace) -> int:
    answers = json.loads(args.answers)
    if not isinstance(answers, dict):
        sys.stderr.write("--answers must decode to a JSON object mapping D1..D6 to option keys.\n")
        return 1
    result = score_diagnostic_answers(answers)
    print(json.dumps(result, indent=2))
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    domains = [x.strip() for x in args.domains.split(",") if x.strip()] if args.domains else None
    spec = synthesize_dyadic_architecture(
        operator_mbti=args.mbti,
        operator_enneagram=args.enneagram,
        operator_instincts=args.instincts,
        operator_name=args.operator_name,
        architect_name=args.architect_name,
        architect_acronym=args.architect_acronym,
        counterweight_mbti_override=args.counterweight_mbti,
        domains=domains,
        custom_notes=args.notes,
    )
    print(json.dumps(spec, indent=2))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    target_dir = Path(args.target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if args.quiz_answers:
        scored = score_diagnostic_answers(json.loads(args.quiz_answers))
        mbti = args.mbti or scored["inferred_operator_mbti"]
        enneagram = args.enneagram or scored["inferred_operator_enneagram"]
        instincts = args.instincts or scored["inferred_operator_instincts"]
        cw_override = args.counterweight_mbti or scored["proposed_architecture"]["architect"]["mbti"]
    else:
        if not args.mbti or not args.enneagram:
            sys.stderr.write("Provide --mbti and --enneagram, or pass --quiz-answers JSON.\n")
            return 1
        mbti = args.mbti
        enneagram = args.enneagram
        instincts = args.instincts or "sp/sx"
        cw_override = args.counterweight_mbti

    domains = [x.strip() for x in args.domains.split(",") if x.strip()] if args.domains else None
    spec = synthesize_dyadic_architecture(
        operator_mbti=mbti,
        operator_enneagram=enneagram,
        operator_instincts=instincts,
        operator_name=args.operator_name,
        architect_name=args.architect_name,
        architect_acronym=args.architect_acronym,
        counterweight_mbti_override=cw_override,
        domains=domains,
        custom_notes=args.notes,
    )

    _copy_agents_tree_if_external(target_dir)
    host_info = detect_host_environment(target_dir)
    today_iso = now_local(host_info["timezone"]).date().isoformat()

    sys_prompt_md = render_system_prompt(spec)
    op_profile_md = render_operator_profile_md(spec, host_info, today_iso)
    routing_md = render_routing_matrix_md(host_info, today_iso)
    sprint_md = render_active_sprint_md(spec, today_iso)
    adr_md = render_archive_decisions_md(spec, host_info, today_iso)
    hydration_md = render_state_hydration_rule(op_profile_md, routing_md, sprint_md)
    hooks_json_str = render_hooks_json(host_info, target_dir, spec["architect"]["name"])
    ws_cfg_str = render_workspace_config_json(
        spec,
        host_info,
        kortex_account=args.kortex_account,
        default_notebook_id=args.notebook_id,
    )

    md_targets = {
        "SYSTEM_PROMPT.md": sys_prompt_md,
        "GEMINI.md": sys_prompt_md,
        ".agents/rules/state-hydration.md": hydration_md,
        "state/operator_profile.md": op_profile_md,
        "state/routing_matrix.md": routing_md,
        "state/active_sprint.md": sprint_md,
        "state/archive_decisions.md": adr_md,
    }
    for rel_path, content in md_targets.items():
        sec_err = lint_security_payload(rel_path, content, check_stored_injection=rel_path.startswith("state/"))
        if sec_err:
            sys.stderr.write(f"Build aborted ({rel_path}): {sec_err}\n")
            return 1
        slop_err = lint_markdown_slop(rel_path, content)
        if slop_err:
            sys.stderr.write(f"Build aborted ({rel_path}): {slop_err}\n")
            return 1

    for rel_path, content in {
        **md_targets,
        "state/workspace_config.json": ws_cfg_str,
        ".agents/hooks.json": hooks_json_str,
    }.items():
        out_path = target_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

    (target_dir / "scratch").mkdir(parents=True, exist_ok=True)
    _ensure_posix_exec_bits(target_dir)

    adr_sha, adr_bytes = file_sha256_and_size(str(target_dir / "state" / "archive_decisions.md"))
    append_locked_audit_entry(
        str(target_dir / "state" / "audit_log.jsonl"),
        {
            "ts": now_local(host_info["timezone"]).isoformat(timespec="seconds"),
            "conv_id": "bootstrap",
            "step_idx": 0,
            "category": "ADR_DECISION",
            "tool": "bootstrap.py:build",
            "target": "ADR-0001",
            "summary": (
                f"ADR-0001: Bootstrapped {spec['architect']['name']} "
                f"({spec['architect']['mbti']} {spec['architect']['enneagram']}) for "
                f"{spec['operator']['name']} ({spec['operator']['mbti']} {spec['operator']['enneagram']} {spec['operator']['instincts']})"
            ),
            "status": "OK",
            "sha256_before": None,
            "sha256_after": adr_sha[:16] if adr_sha else None,
            "bytes_after": adr_bytes,
            "mutated": True,
            "git_head": git_head_short(str(target_dir)),
        },
        tz_name=host_info["timezone"],
    )

    report = verify_installation(target_dir)
    report["operator"] = spec["operator"]
    report["architect"] = {
        k: v for k, v in spec["architect"].items() if k != "protocols"
    }
    report["host"] = host_info
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "VERIFIED" else 1


def cmd_refresh_hydration(args: argparse.Namespace) -> int:
    target_dir = Path(args.target_dir).resolve()
    op_p = target_dir / "state" / "operator_profile.md"
    rt_p = target_dir / "state" / "routing_matrix.md"
    sp_p = target_dir / "state" / "active_sprint.md"
    for req in (op_p, rt_p, sp_p):
        if not req.is_file():
            sys.stderr.write(f"Missing required state file: {req}\n")
            return 1
    hydration_md = render_state_hydration_rule(
        op_p.read_text(encoding="utf-8"),
        rt_p.read_text(encoding="utf-8"),
        sp_p.read_text(encoding="utf-8"),
    )
    slop_err = lint_markdown_slop(".agents/rules/state-hydration.md", hydration_md)
    if slop_err:
        sys.stderr.write(f"{slop_err}\n")
        return 1
    out_p = target_dir / ".agents" / "rules" / "state-hydration.md"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(hydration_md, encoding="utf-8")
    print(json.dumps({"status": "OK", "updated": str(out_p)}, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    target_dir = Path(args.target_dir).resolve()
    rep = verify_installation(target_dir)
    print(json.dumps(rep, indent=2))
    return 0 if rep.get("status") == "VERIFIED" else 1


def cmd_reset_bootstrap(args: argparse.Namespace) -> int:
    if not args.confirm:
        sys.stderr.write("Pass --confirm to reset workspace back to unconfigured Bootstrap Mode.\n")
        return 1
    target_dir = Path(args.target_dir).resolve()
    tmpl = STARTER_ROOT / "templates" / "bootstrap_gemini.md"
    if not tmpl.is_file():
        sys.stderr.write(f"Missing template: {tmpl}\n")
        return 1
    shutil.copy2(tmpl, target_dir / "GEMINI.md")
    for rel_rm in (
        "SYSTEM_PROMPT.md",
        ".agents/hooks.json",
        ".agents/rules/state-hydration.md",
        "state/workspace_config.json",
        "state/operator_profile.md",
        "state/routing_matrix.md",
        "state/active_sprint.md",
        "state/archive_decisions.md",
        "state/audit_log.jsonl",
        "state/audit_log.jsonl.lock",
        "state/.pre_tool_hashes.json",
        "state/epistemic_manifest.json",
    ):
        fp = target_dir / rel_rm
        if fp.is_file():
            fp.unlink()
    print(json.dumps({"status": "RESET_TO_BOOTSTRAP", "workspace": str(target_dir)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Self-Assembling Dyadic Co-Architect Bootstrap Engine")
    sub = p.add_subparsers(dest="subcmd", required=True)

    s_det = sub.add_parser("detect", help="Inspect host OS, Python runtime, shell, and timezone")
    s_det.add_argument("--target-dir", default=str(STARTER_ROOT))

    s_grl = sub.add_parser("grill", help="Print the 6-dilemma cognitive diagnostic questions")
    s_grl.add_argument("--format", choices=("json", "text"), default="json")

    s_scr = sub.add_parser("score-quiz", help="Score D1..D6 diagnostic answers into a proposed pairing")
    s_scr.add_argument("--answers", required=True, help="JSON dict mapping D1..D6 to option keys")

    s_prv = sub.add_parser("preview", help="Preview a synthesized Co-Architect spec without writing files")
    s_prv.add_argument("--mbti", required=True)
    s_prv.add_argument("--enneagram", required=True)
    s_prv.add_argument("--instincts", default="sp/sx")
    s_prv.add_argument("--operator-name", default="Operator")
    s_prv.add_argument("--architect-name", default="")
    s_prv.add_argument("--architect-acronym", default="")
    s_prv.add_argument("--counterweight-mbti", default="")
    s_prv.add_argument("--domains", default="")
    s_prv.add_argument("--notes", default="")

    s_bld = sub.add_parser("build", help="Assemble Co-Architect, install cross-platform hooks, and verify")
    s_bld.add_argument("--target-dir", default=str(STARTER_ROOT))
    s_bld.add_argument("--mbti", default="")
    s_bld.add_argument("--enneagram", default="")
    s_bld.add_argument("--instincts", default="sp/sx")
    s_bld.add_argument("--quiz-answers", default="", help="Optional JSON dict of D1..D6 answers")
    s_bld.add_argument("--operator-name", default="Operator")
    s_bld.add_argument("--architect-name", default="")
    s_bld.add_argument("--architect-acronym", default="")
    s_bld.add_argument("--counterweight-mbti", default="")
    s_bld.add_argument("--domains", default="", help="Comma-separated focus domains")
    s_bld.add_argument("--notes", default="", help="Additional operator preferences or context")
    s_bld.add_argument("--kortex-account", default="")
    s_bld.add_argument("--notebook-id", default="")

    s_hyd = sub.add_parser("refresh-hydration", help="Re-sync .agents/rules/state-hydration.md from state/*.md")
    s_hyd.add_argument("--target-dir", default=str(STARTER_ROOT))

    s_ver = sub.add_parser("verify", help="Run live verification checks on an installed workspace")
    s_ver.add_argument("--target-dir", default=str(STARTER_ROOT))

    s_rst = sub.add_parser("reset-bootstrap", help="Restore repository to unconfigured Bootstrap Mode")
    s_rst.add_argument("--target-dir", default=str(STARTER_ROOT))
    s_rst.add_argument("--confirm", action="store_true")

    return p


def main() -> int:
    args = build_parser().parse_args()
    dispatch = {
        "detect": cmd_detect,
        "grill": cmd_grill,
        "score-quiz": cmd_score_quiz,
        "preview": cmd_preview,
        "build": cmd_build,
        "refresh-hydration": cmd_refresh_hydration,
        "verify": cmd_verify,
        "reset-bootstrap": cmd_reset_bootstrap,
    }
    return dispatch[args.subcmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
