#!/usr/bin/env python3
"""Cross-Platform Clean-Room Staging, Sharded Context Bundler, & Snapshot Manager for `/iterate`.

Zero external dependencies (Python 3.9+ stdlib). Enforces:
- Zero default live workspace mutation during iteration rounds.
- `<760`-line / `<=44KB` sharded Round 1 context bundles for truncation-free `read_file` calls.
- Round 2+ unified diff bundles with `DELETED:<path>` symmetry across status, diff, and apply.
- Staged `.md` (`human-voice.md` anti-slop), `.py` (`ast.parse`), `.json` (`json.loads`), and
  invisible Unicode validation before recording round snapshots.
- Supermajority consensus & zero-delta early-stop circuit breaker.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

for _cand in (
    Path(__file__).resolve().parents[3] / "scripts",
    Path.cwd().resolve() / ".agents" / "scripts",
):
    if _cand.is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))

from core_hooks import HIDDEN_UNICODE_RE, lint_markdown_slop  # noqa: E402

IGNORE_NAMES = {
    ".git",
    "__pycache__",
    ".DS_Store",
    "Thumbs.db",
    ".iterate_stage",
    "iterate_stage",
    ".venv",
    "venv",
    "node_modules",
}

MAX_BUNDLE_SHARD_LINES = 760
MAX_BUNDLE_SHARD_CHARS = 44000


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_tree_stats(root: Path) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return stats
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in IGNORE_NAMES]
        for fn in sorted(filenames):
            if fn in IGNORE_NAMES:
                continue
            full = Path(dirpath) / fn
            if not full.is_file():
                continue
            rel = full.relative_to(root).as_posix()
            stats[rel] = {"sha256": sha256_file(full), "bytes": full.stat().st_size}
    return stats


def _copy_filtered(src: Path, dst: Path) -> None:
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in sorted(dirnames) if d not in IGNORE_NAMES]
        rel_dir = Path(dirpath).relative_to(src)
        target_dir = dst / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        for fn in sorted(filenames):
            if fn in IGNORE_NAMES:
                continue
            s_file = Path(dirpath) / fn
            if s_file.is_file():
                shutil.copy2(s_file, target_dir / fn)


def _write_context_shards(stage_dir: Path, current_dir: Path) -> list[str]:
    stats = collect_tree_stats(current_dir)
    shards: list[list[str]] = [[]]
    cur_lines = 0
    cur_chars = 0

    for rel in sorted(stats.keys()):
        f_path = current_dir / rel
        try:
            text = f_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = f"[Binary file omitted: {rel} ({stats[rel]['bytes']} bytes)]\n"
        block = f"=== FILE: {rel} ===\n{text.rstrip()}\n=== END FILE: {rel} ===\n\n"
        b_lines = block.count("\n")
        b_chars = len(block)
        if shards[-1] and (
            cur_lines + b_lines > MAX_BUNDLE_SHARD_LINES or cur_chars + b_chars > MAX_BUNDLE_SHARD_CHARS
        ):
            shards.append([])
            cur_lines = 0
            cur_chars = 0
        shards[-1].append(block)
        cur_lines += b_lines
        cur_chars += b_chars

    out_paths: list[str] = []
    for idx, blocks in enumerate(shards, start=1):
        if not blocks:
            continue
        sp = stage_dir / f"round_1_context_bundle_part{idx}.txt"
        sp.write_text("".join(blocks), encoding="utf-8")
        out_paths.append(str(sp.resolve()))
    return out_paths


def _validate_tree(current_dir: Path) -> tuple[list[str], list[str]]:
    slop_errors: list[str] = []
    syntax_errors: list[str] = []
    for rel in sorted(collect_tree_stats(current_dir).keys()):
        fp = current_dir / rel
        try:
            txt = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if HIDDEN_UNICODE_RE.search(txt):
            syntax_errors.append(f"{rel}: hidden Unicode/bidi control character detected")
        if rel.lower().endswith(".md"):
            err = lint_markdown_slop(rel, txt)
            if err:
                slop_errors.append(f"{rel}: {err}")
        elif rel.lower().endswith(".py"):
            try:
                ast.parse(txt, filename=rel)
            except SyntaxError as exc:
                syntax_errors.append(f"{rel}:{exc.lineno}: Python SyntaxError: {exc.msg}")
        elif rel.lower().endswith(".json"):
            try:
                json.loads(txt)
            except json.JSONDecodeError as exc:
                syntax_errors.append(f"{rel}:{exc.lineno}: JSONDecodeError: {exc.msg}")
    return slop_errors, syntax_errors


def _compute_deltas(prev_stats: dict[str, Any], cur_stats: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    all_keys = sorted(set(prev_stats.keys()) | set(cur_stats.keys()))
    for k in all_keys:
        if k not in cur_stats:
            changed.append(f"DELETED:{k}")
        elif k not in prev_stats or prev_stats[k]["sha256"] != cur_stats[k]["sha256"]:
            changed.append(k)
    return changed


def _build_unified_diff(prev_dir: Path, cur_dir: Path, deltas: list[str]) -> str:
    chunks: list[str] = []
    for item in deltas:
        if item.startswith("DELETED:"):
            rel = item.split(":", 1)[1]
            chunks.append(f"--- a/{rel}\n+++ /dev/null\n@@ DELETED:{rel} @@\n")
            continue
        rel = item
        old_p = prev_dir / rel
        new_p = cur_dir / rel
        old_lines = (
            old_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            if old_p.is_file()
            else []
        )
        new_lines = (
            new_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            if new_p.is_file()
            else []
        )
        diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{rel}", tofile=f"b/{rel}")
        chunks.append("".join(diff))
    return "\n".join(chunks) + ("\n" if chunks else "")


def cmd_init(args: argparse.Namespace) -> int:
    stage_dir = Path(args.stage_dir).resolve()
    if args.reset and stage_dir.exists():
        shutil.rmtree(stage_dir)
    current_dir = stage_dir / "current"
    baseline_dir = stage_dir / "rounds" / "round_0_baseline"
    current_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)

    sources_meta: list[dict[str, str]] = []
    for raw_src in args.source:
        sp = Path(raw_src).resolve()
        if not sp.exists():
            sys.stderr.write(f"Source path not found: {sp}\n")
            return 1
        if sp.is_dir():
            _copy_filtered(sp, current_dir)
            sources_meta.append({"source": str(sp), "mode": "dir", "rel": "."})
        else:
            dst = current_dir / sp.name
            _copy_filtered(sp, dst)
            sources_meta.append({"source": str(sp), "mode": "file", "rel": sp.name})

    _copy_filtered(current_dir, baseline_dir)
    shards = _write_context_shards(stage_dir, current_dir)
    manifest = {
        "initialized_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources_meta,
        "current_round": 0,
        "converged": False,
        "round_1_context_bundle_paths": shards,
        "rounds": [],
    }
    (stage_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "INITIALIZED",
                "stage_current": str(current_dir),
                "files_staged": len(collect_tree_stats(current_dir)),
                "round_1_context_bundle_paths": shards,
            },
            indent=2,
        )
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    stage_dir = Path(args.stage_dir).resolve()
    m_path = stage_dir / "manifest.json"
    if not m_path.is_file():
        print(json.dumps({"status": "UNINITIALIZED"}))
        return 1
    manifest = json.loads(m_path.read_text(encoding="utf-8"))
    if args.reopen:
        manifest["converged"] = False
        m_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if args.require_unconverged and manifest.get("converged"):
        print(json.dumps({"status": "CONVERGENCE_CIRCUIT_BREAKER_ACTIVE", "round": manifest.get("current_round")}))
        return 2
    prev_round = manifest["current_round"]
    prev_dir = (
        stage_dir / "rounds" / "round_0_baseline"
        if prev_round == 0
        else stage_dir / "rounds" / f"round_{prev_round}"
    )
    deltas = _compute_deltas(collect_tree_stats(prev_dir), collect_tree_stats(stage_dir / "current"))
    print(
        json.dumps(
            {
                "status": "ACTIVE",
                "current_round": prev_round,
                "converged": manifest.get("converged", False),
                "uncommitted_stage_deltas": deltas,
            },
            indent=2,
        )
    )
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    stage_dir = Path(args.stage_dir).resolve()
    baseline_dir = stage_dir / "rounds" / "round_0_baseline"
    current_dir = stage_dir / "current"
    deltas = _compute_deltas(collect_tree_stats(baseline_dir), collect_tree_stats(current_dir))
    sys.stdout.write(_build_unified_diff(baseline_dir, current_dir, deltas))
    return 0


def cmd_snapshot_round(args: argparse.Namespace) -> int:
    stage_dir = Path(args.stage_dir).resolve()
    m_path = stage_dir / "manifest.json"
    manifest = json.loads(m_path.read_text(encoding="utf-8"))
    current_dir = stage_dir / "current"

    slop_errs, syn_errs = _validate_tree(current_dir)
    if slop_errs or syn_errs:
        print(
            json.dumps(
                {
                    "status": "VALIDATION_FAILED",
                    "slop_lint": slop_errs or "PASS",
                    "syntax_lint": syn_errs or "PASS",
                },
                indent=2,
            )
        )
        return 1

    prev_num = int(manifest.get("current_round") or 0)
    next_num = prev_num + 1
    prev_dir = (
        stage_dir / "rounds" / "round_0_baseline"
        if prev_num == 0
        else stage_dir / "rounds" / f"round_{prev_num}"
    )
    round_dir = stage_dir / "rounds" / f"round_{next_num}"
    if round_dir.exists():
        shutil.rmtree(round_dir)
    _copy_filtered(current_dir, round_dir)

    deltas = _compute_deltas(collect_tree_stats(prev_dir), collect_tree_stats(round_dir))
    diff_patch = _build_unified_diff(prev_dir, round_dir, deltas)
    diff_path = stage_dir / f"round_{next_num}_diff_bundle.patch"
    diff_path.write_text(diff_patch, encoding="utf-8")

    zero_delta = len(deltas) == 0
    hard_defects = int(args.hard_defects)
    p_size = int(args.panel_size) if args.panel_size else 0
    c_seats = int(args.converged_seats) if args.converged_seats is not None else 0

    quorum_met = False
    if p_size >= 7 and c_seats >= 5:
        quorum_met = True
    elif 3 <= p_size < 7 and c_seats >= 2:
        quorum_met = True
    elif p_size == 2 and (c_seats == 2 or args.primary_lead_converged):
        quorum_met = True
    elif p_size == 0 and zero_delta:
        quorum_met = True

    converged = bool(zero_delta and hard_defects == 0 and quorum_met)
    rec = {
        "round": next_num,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": args.summary,
        "files_changed_vs_prev": deltas,
        "converged_seats": c_seats,
        "panel_size": p_size,
        "hard_defects": hard_defects,
        "converged": converged,
        "diff_bundle": str(diff_path),
    }
    manifest["current_round"] = next_num
    manifest["converged"] = converged
    manifest.setdefault("rounds", []).append(rec)
    m_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "CONVERGED_HALT" if converged else "SNAPSHOT_RECORDED",
                "round": next_num,
                "slop_lint": "PASS",
                "files_changed_vs_prev": deltas,
                "halt_remaining_rounds": converged,
                "diff_bundle": str(diff_path),
            },
            indent=2,
        )
    )
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    stage_dir = Path(args.stage_dir).resolve()
    baseline_dir = stage_dir / "rounds" / "round_0_baseline"
    current_dir = stage_dir / "current"
    target_dir = Path(args.target).resolve()

    slop_errs, syn_errs = _validate_tree(current_dir)
    if slop_errs or syn_errs:
        print(json.dumps({"status": "VALIDATION_FAILED", "slop": slop_errs, "syntax": syn_errs}, indent=2))
        return 1

    deltas = _compute_deltas(collect_tree_stats(baseline_dir), collect_tree_stats(current_dir))
    applied: list[str] = []
    for item in deltas:
        if item.startswith("DELETED:"):
            rel = item.split(":", 1)[1]
            dst = target_dir / rel
            if dst.is_file():
                dst.unlink()
                applied.append(item)
        else:
            src = current_dir / item
            dst = target_dir / item
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            applied.append(item)

    print(json.dumps({"status": "APPLIED", "target": str(target_dir), "applied": applied}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Clean-room staging manager for /iterate")
    sub = p.add_subparsers(dest="subcmd", required=True)

    s_init = sub.add_parser("init")
    s_init.add_argument("--stage-dir", required=True)
    s_init.add_argument("--source", action="append", required=True)
    s_init.add_argument("--reset", action="store_true")

    s_stat = sub.add_parser("status")
    s_stat.add_argument("--stage-dir", required=True)
    s_stat.add_argument("--require-unconverged", action="store_true")
    s_stat.add_argument("--reopen", action="store_true")

    s_diff = sub.add_parser("diff")
    s_diff.add_argument("--stage-dir", required=True)

    s_snap = sub.add_parser("snapshot-round")
    s_snap.add_argument("--stage-dir", required=True)
    s_snap.add_argument("--converged-seats", type=int, default=0)
    s_snap.add_argument("--panel-size", type=int, default=0)
    s_snap.add_argument("--hard-defects", type=int, default=0)
    s_snap.add_argument("--primary-lead-converged", action="store_true")
    s_snap.add_argument("--summary", required=True)

    s_app = sub.add_parser("apply")
    s_app.add_argument("--stage-dir", required=True)
    s_app.add_argument("--target", required=True)
    return p


def main() -> int:
    args = build_parser().parse_args()
    dispatch = {
        "init": cmd_init,
        "status": cmd_status,
        "diff": cmd_diff,
        "snapshot-round": cmd_snapshot_round,
        "apply": cmd_apply,
    }
    return dispatch[args.subcmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
