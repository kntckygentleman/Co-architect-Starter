#!/usr/bin/env python3
"""Zero-dependency automated test suite for `coarchitect-starter`."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / ".agents" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from core_hooks import (  # noqa: E402
    REQUIRED_PERSONA_MARKERS,
    VALID_SEAT_IDENTITY_RE,
    lint_markdown_slop,
    lint_security_payload,
)
from engine.cognitive_matrix import (  # noqa: E402
    DIAGNOSTIC_DILEMMAS,
    INSTINCT_CALIBRATIONS,
    MBTI_STACKS,
    score_diagnostic_answers,
    synthesize_dyadic_architecture,
)
from engine.host_probe import detect_host_environment, format_hook_command  # noqa: E402
from engine.renderer import render_system_prompt  # noqa: E402


class TestCognitiveMatrixAndScoring(unittest.TestCase):
    def test_all_16_mbti_9_enneagram_6_instincts_render_slop_free(self) -> None:
        instinct_keys = list(INSTINCT_CALIBRATIONS.keys())
        sample_wings = ("1w9", "2w1", "3w4", "4w3", "5w6", "6w5", "7w8", "8w7", "9w1")
        for idx, mbti in enumerate(sorted(MBTI_STACKS.keys())):
            ennea = sample_wings[idx % len(sample_wings)]
            inst = instinct_keys[idx % len(instinct_keys)]
            spec = synthesize_dyadic_architecture(
                operator_mbti=mbti,
                operator_enneagram=ennea,
                operator_instincts=inst,
                operator_name="Jordan",
                domains=["Product Engineering", "Writing"],
            )
            prompt_md = render_system_prompt(spec)
            self.assertIsNone(
                lint_markdown_slop("SYSTEM_PROMPT.md", prompt_md),
                msg=f"Slop lint failed for {mbti} {ennea} {inst}",
            )
            self.assertIsNone(lint_security_payload("SYSTEM_PROMPT.md", prompt_md, check_stored_injection=False))
            for marker in REQUIRED_PERSONA_MARKERS:
                self.assertIn(marker, prompt_md, msg=f"Missing {marker} for {mbti}")

    def test_entp_7w8_spsx_vs_entp_5w4_sosp_differentiation(self) -> None:
        spec_7w8 = synthesize_dyadic_architecture(
            operator_mbti="ENTP",
            operator_enneagram="7w8",
            operator_instincts="sp/sx",
            operator_name="PartnerA",
        )
        spec_5w4 = synthesize_dyadic_architecture(
            operator_mbti="ENTP",
            operator_enneagram="5w4",
            operator_instincts="so/sp",
            operator_name="PartnerB",
        )
        self.assertEqual(spec_7w8["architect"]["mbti"], "INTJ")
        self.assertEqual(spec_5w4["architect"]["mbti"], "INTJ")
        self.assertEqual(spec_7w8["architect"]["enneagram"], "1w9 (with 5w6 Anchor)")
        self.assertEqual(spec_5w4["architect"]["enneagram"], "8w9 (with 3w4 Anchor)")
        self.assertIn("high-conviction deep work", spec_7w8["architect"]["bandwidth_defense_rule"])
        self.assertIn("sx blind spot", spec_5w4["architect"]["bandwidth_defense_rule"])

    def test_diagnostic_grilling_scorer(self) -> None:
        self.assertEqual(len(DIAGNOSTIC_DILEMMAS), 6)
        res_enfp = score_diagnostic_answers(
            {
                "D1": "Ne",
                "D2": "Fi",
                "D3": "Ne_loop",
                "D4": "5w4",
                "D5": "sp/so",
                "D6": "studio",
            }
        )
        self.assertEqual(res_enfp["inferred_operator_mbti"], "ENFP")
        self.assertEqual(res_enfp["inferred_operator_enneagram"], "5w4")
        self.assertEqual(res_enfp["inferred_operator_instincts"], "sp/so")
        self.assertEqual(res_enfp["proposed_architecture"]["architect"]["mbti"], "INTJ")

        res_intp = score_diagnostic_answers(
            {
                "D1": "Ne",
                "D2": "Ti",
                "D3": "Ti_loop",
                "D4": "5w6",
                "D5": "sp/sx",
                "D6": "commander",
            }
        )
        self.assertIn(res_intp["inferred_operator_mbti"], ("INTP", "ENTP"))
        self.assertEqual(res_intp["proposed_architecture"]["architect"]["mbti"], "ENTJ")


class TestHostProbeAndCrossPlatformFormatting(unittest.TestCase):
    def test_host_detection_fields(self) -> None:
        info = detect_host_environment(REPO_ROOT)
        for key in (
            "os_system",
            "os_family",
            "machine_arch",
            "python_version",
            "python_hook_invoker",
            "file_lock_backend",
            "timezone",
            "detected_platforms",
            "sample_hook_command",
        ):
            self.assertIn(key, info)
        self.assertIn("agents_md", info["detected_platforms"])
        self.assertIn(info["file_lock_backend"], ("fcntl", "msvcrt"))

    def test_hook_command_quoting_with_spaces_and_windows(self) -> None:
        spaced_path = Path("/tmp/My Workspace Folder/.agents/scripts/workspace_hooks.py")
        cmd = format_hook_command("python3", spaced_path, "PreToolUse")
        self.assertIn('"', cmd)
        self.assertTrue(cmd.endswith(" PreToolUse"))

        with mock.patch("os.name", "nt"):
            win_cmd = format_hook_command(
                '"C:/Program Files/Python312/python.exe"',
                spaced_path,
                "SessionStart",
            )
            self.assertNotIn("\\", win_cmd)
            self.assertTrue(win_cmd.endswith(" SessionStart"))


class TestEndToEndBootstrapHooksAndIterate(unittest.TestCase):
    def test_full_build_hooks_adr_and_iterate_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "test space"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "bootstrap.py"),
                    "build",
                    "--target-dir",
                    str(ws),
                    "--operator-name",
                    "Casey",
                    "--mbti",
                    "ENTP",
                    "--enneagram",
                    "7w8",
                    "--instincts",
                    "sp/sx",
                    "--architect-name",
                    "Vera",
                    "--platform",
                    "all",
                    "--domains",
                    "Systems Design, Writing, Product Strategy",
                ],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            rep = json.loads(proc.stdout)
            self.assertEqual(rep["status"], "VERIFIED")
            self.assertEqual(rep["architect_name"], "Vera")
            self.assertEqual(rep["debug_phrase"], "[Vera Debug Mode]")
            self.assertTrue((ws / "ssot" / "00_STATE_PROJECT_CANON.md").is_file())
            self.assertTrue((ws / "AGENTS.md").is_file())
            self.assertTrue((ws / "CLAUDE.md").is_file())
            self.assertTrue((ws / "GEMINI.md").is_file())
            self.assertTrue((ws / ".claude" / "settings.json").is_file())
            self.assertTrue((ws / ".cursor" / "rules" / "coarchitect.mdc").is_file())

            hooks_script = ws / ".agents" / "scripts" / "workspace_hooks.py"
            audit_script = ws / ".agents" / "scripts" / "audit_log.py"
            iterate_script = ws / ".agents" / "skills" / "iterate" / "scripts" / "iterate_stage.py"
            env = {**os.environ, "COARCHITECT_WORKSPACE_ROOT": str(ws)}

            # 1. Debug mode allows editing locked SYSTEM_PROMPT.md; non-debug blocks shell mutation
            shell_block = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "conversationId": "t1",
                        "lastUserInput": "append a line",
                        "toolCall": {
                            "name": "run_command",
                            "args": {"CommandLine": "echo hacked >> SYSTEM_PROMPT.md"},
                        },
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(json.loads(shell_block.stdout)["decision"], "deny")

            debug_allow = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "conversationId": "t1",
                        "lastUserInput": "[Vera Debug Mode] minor note",
                        "toolCall": {
                            "name": "edit_file",
                            "args": {
                                "Path": str(ws / "SYSTEM_PROMPT.md"),
                                "Target": "Casey",
                                "Replacement": "Casey",
                            },
                        },
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(json.loads(debug_allow.stdout)["decision"], "allow")

            # 2. Subagent model tiering gate
            sub_deny_inherit = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "conversationId": "t1",
                        "lastUserInput": "Run council",
                        "toolCall": {
                            "name": "invoke_subagent",
                            "args": {
                                "TypeName": "council-intj",
                                "Role": "Strategist",
                                "Prompt": "Audit plan",
                                "Model": "inherit",
                            },
                        },
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(json.loads(sub_deny_inherit.stdout)["decision"], "deny")

            sub_allow_pro = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "conversationId": "t1",
                        "lastUserInput": "Run council",
                        "toolCall": {
                            "name": "invoke_subagent",
                            "args": {
                                "TypeName": "council-intj",
                                "Role": "Strategist",
                                "Prompt": "Audit plan",
                                "Model": "pro",
                            },
                        },
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(json.loads(sub_allow_pro.stdout)["decision"], "allow")

            # 3. Record ADR-0002 & verify SHA-256 chain
            adr_proc = subprocess.run(
                [
                    sys.executable,
                    str(audit_script),
                    "record-adr",
                    "--title",
                    "Adopt Weekly Creative Sprint Block",
                    "--context",
                    "Fragmented afternoons slowed creative completion.",
                    "--decision",
                    "Reserve Tuesday and Thursday mornings for solo creative builds.",
                    "--consequences",
                    "Admin meetings move to afternoon slots.",
                ],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(adr_proc.returncode, 0, msg=adr_proc.stderr)
            self.assertEqual(json.loads(adr_proc.stdout)["adr_id"], "ADR-0002")

            ver_proc = subprocess.run(
                [sys.executable, str(audit_script), "verify"],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(ver_proc.returncode, 0)
            self.assertGreaterEqual(json.loads(ver_proc.stdout)["verified_entries"], 3)

            # 4. Test clean-room /iterate staging engine
            sample_doc = ws / "draft_spec.md"
            sample_doc.write_text("# Draft Spec\n\nInitial plain version.\n", encoding="utf-8")
            stage_dir = ws / "scratch" / "iterate_stage"

            init_p = subprocess.run(
                [
                    sys.executable,
                    str(iterate_script),
                    "init",
                    "--stage-dir",
                    str(stage_dir),
                    "--source",
                    str(sample_doc),
                    "--reset",
                ],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(init_p.returncode, 0, msg=init_p.stderr)

            (stage_dir / "current" / "draft_spec.md").write_text(
                "# Draft Spec\n\nUpdated clean version after Round 1 review.\n",
                encoding="utf-8",
            )
            snap_1 = subprocess.run(
                [
                    sys.executable,
                    str(iterate_script),
                    "snapshot-round",
                    "--stage-dir",
                    str(stage_dir),
                    "--converged-seats",
                    "2",
                    "--panel-size",
                    "3",
                    "--hard-defects",
                    "1",
                    "--summary",
                    "Round 1 update",
                ],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(snap_1.returncode, 0)
            self.assertEqual(json.loads(snap_1.stdout)["status"], "SNAPSHOT_RECORDED")

            snap_2 = subprocess.run(
                [
                    sys.executable,
                    str(iterate_script),
                    "snapshot-round",
                    "--stage-dir",
                    str(stage_dir),
                    "--converged-seats",
                    "2",
                    "--panel-size",
                    "2",
                    "--hard-defects",
                    "0",
                    "--summary",
                    "Round 2 converged",
                ],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(snap_2.returncode, 0)
            self.assertEqual(json.loads(snap_2.stdout)["status"], "CONVERGED_HALT")

            app_p = subprocess.run(
                [
                    sys.executable,
                    str(iterate_script),
                    "apply",
                    "--stage-dir",
                    str(stage_dir),
                    "--target",
                    str(ws),
                ],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(app_p.returncode, 0)
            self.assertIn("Updated clean version", sample_doc.read_text(encoding="utf-8"))

    def test_multiplatform_obsidian_ssot_git_hook_and_claude_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "universal_ws"
            ws.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "-C", str(ws), "init", "-q"], check=True)
            tmpl = REPO_ROOT / "templates" / "bootstrap_onboarding.md"
            for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
                (ws / name).write_text(tmpl.read_text(encoding="utf-8"), encoding="utf-8")

            build_proc = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "bootstrap.py"),
                    "build",
                    "--target-dir",
                    str(ws),
                    "--operator-name",
                    "Morgan",
                    "--mbti",
                    "INTP",
                    "--enneagram",
                    "5w6",
                    "--instincts",
                    "sp/sx",
                    "--platform",
                    "all",
                    "--ssot",
                    "obsidian",
                    "--ssot-target",
                    "~/Notes/ProjectCanon.md",
                    "--install-git-hook",
                ],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(build_proc.returncode, 0, msg=build_proc.stderr + "\n" + build_proc.stdout)
            rep = json.loads(build_proc.stdout)
            self.assertEqual(rep["status"], "VERIFIED")
            self.assertEqual(rep["ssot"]["backend"], "obsidian")
            self.assertEqual(rep["ssot"]["target"], "~/Notes/ProjectCanon.md")
            self.assertTrue(rep["git_hook_installed"])

            sys_txt = (ws / "SYSTEM_PROMPT.md").read_text(encoding="utf-8")
            self.assertEqual((ws / "AGENTS.md").read_text(encoding="utf-8"), sys_txt)
            self.assertEqual((ws / "CLAUDE.md").read_text(encoding="utf-8"), sys_txt)
            self.assertEqual((ws / "GEMINI.md").read_text(encoding="utf-8"), sys_txt)
            self.assertFalse((ws / "ssot" / "00_STATE_PROJECT_CANON.md").exists())
            claude_cfg = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
            self.assertIn("PreToolUse", claude_cfg["hooks"])
            self.assertIn("alwaysApply: true", (ws / ".cursor" / "rules" / "coarchitect.mdc").read_text(encoding="utf-8"))
            pre_commit = ws / ".git" / "hooks" / "pre-commit"
            self.assertTrue(pre_commit.is_file())
            self.assertIn("check-files --staged", pre_commit.read_text(encoding="utf-8"))

            hooks_script = ws / ".agents" / "scripts" / "workspace_hooks.py"
            env = {**os.environ, "COARCHITECT_WORKSPACE_ROOT": str(ws)}

            # Claude Code Write to locked file -> exit code 2 + hookSpecificOutput deny
            claude_lock = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "session_id": "claude-s1",
                        "hook_event_name": "PreToolUse",
                        "tool_name": "Write",
                        "tool_input": {"file_path": str(ws / "CLAUDE.md"), "content": "# overwrite"},
                        "prompt": "update rules",
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(claude_lock.returncode, 2)
            self.assertTrue(claude_lock.stderr.strip())
            claude_lock_out = json.loads(claude_lock.stdout)
            self.assertEqual(claude_lock_out["hookSpecificOutput"]["permissionDecision"], "deny")

            # Claude Code MultiEdit anti-slop -> exit code 2
            claude_slop = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "session_id": "claude-s1",
                        "hook_event_name": "PreToolUse",
                        "tool_name": "MultiEdit",
                        "tool_input": {
                            "file_path": str(ws / "state" / "active_sprint.md"),
                            "edits": [{"old_string": "a", "new_string": "Wait \u2014 let us delve in."}],
                        },
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(claude_slop.returncode, 2)
            self.assertEqual(
                json.loads(claude_slop.stdout)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

            # Claude Code Bash reading .env -> exit code 2
            claude_bash = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "session_id": "claude-s1",
                        "hook_event_name": "PreToolUse",
                        "tool_name": "Bash",
                        "tool_input": {"command": "cat .env.production"},
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(claude_bash.returncode, 2)

            # Claude Code Task haiku worker allowed; sonnet on research denied
            claude_task_ok = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "session_id": "claude-s1",
                        "hook_event_name": "PreToolUse",
                        "tool_name": "Task",
                        "tool_input": {
                            "subagent_type": "research",
                            "description": "scan repo",
                            "prompt": "Find tests",
                            "model": "haiku",
                        },
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(claude_task_ok.returncode, 0)
            self.assertEqual(
                json.loads(claude_task_ok.stdout)["hookSpecificOutput"]["permissionDecision"],
                "allow",
            )

            claude_task_bad = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "session_id": "claude-s1",
                        "hook_event_name": "PreToolUse",
                        "tool_name": "Agent",
                        "tool_input": {
                            "subagent_type": "research",
                            "description": "scan repo",
                            "prompt": "Find tests",
                            "model": "sonnet",
                        },
                    }
                ),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(claude_task_bad.returncode, 2)

            # check-files CLI blocks locked files unless COARCHITECT_DEBUG=1 and blocks slop in .md
            chk_locked = subprocess.run(
                [sys.executable, str(hooks_script), "check-files", str(ws / "SYSTEM_PROMPT.md")],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(chk_locked.returncode, 1)

            chk_debug = subprocess.run(
                [sys.executable, str(hooks_script), "check-files", str(ws / "SYSTEM_PROMPT.md")],
                text=True,
                capture_output=True,
                env={**env, "COARCHITECT_DEBUG": "1"},
                check=False,
            )
            self.assertEqual(chk_debug.returncode, 0)

            bad_note = ws / "notes.md"
            bad_note.write_text("Clean sentence \u2014 wait no, em dash.\n", encoding="utf-8")
            chk_slop = subprocess.run(
                [sys.executable, str(hooks_script), "check-files", str(bad_note)],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(chk_slop.returncode, 1)

            # Claude SessionStart reports mismatch in hookSpecificOutput
            (ws / "CLAUDE.md").write_text("# drifted\n", encoding="utf-8")
            claude_sess = subprocess.run(
                [sys.executable, str(hooks_script), "SessionStart"],
                input=json.dumps({"session_id": "claude-s1", "hook_event_name": "SessionStart"}),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(claude_sess.returncode, 0)
            sess_data = json.loads(claude_sess.stdout)
            self.assertEqual(sess_data["hookSpecificOutput"]["hookEventName"], "SessionStart")
            self.assertIn("SHA-256 mismatch", sess_data["hookSpecificOutput"]["additionalContext"])

            # Explicit single-platform build cleans stale bootstrap GEMINI.md; reset restores all 3
            claude_only = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "bootstrap.py"),
                    "reset-bootstrap",
                    "--target-dir",
                    str(ws),
                    "--confirm",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(claude_only.returncode, 0)
            self.assertTrue((ws / "AGENTS.md").is_file())
            self.assertTrue((ws / "CLAUDE.md").is_file())
            self.assertTrue((ws / "GEMINI.md").is_file())
            self.assertFalse((ws / ".claude" / "settings.json").exists())

            claude_single = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "bootstrap.py"),
                    "build",
                    "--target-dir",
                    str(ws),
                    "--operator-name",
                    "Morgan",
                    "--mbti",
                    "INTP",
                    "--enneagram",
                    "5w6",
                    "--instincts",
                    "sp/sx",
                    "--platform",
                    "claude",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(claude_single.returncode, 0, msg=claude_single.stderr + "\n" + claude_single.stdout)
            self.assertEqual(json.loads(claude_single.stdout)["status"], "VERIFIED")
            self.assertFalse((ws / "GEMINI.md").exists())
            self.assertTrue((ws / "ssot" / "00_STATE_PROJECT_CANON.md").is_file())


class TestStarterRepoSlopAndZeroPII(unittest.TestCase):
    def test_all_starter_markdown_and_zero_pii(self) -> None:
        self.assertTrue((REPO_ROOT / "llms.txt").is_file())
        self.assertTrue((REPO_ROOT / "AGENTS.md").is_file())
        self.assertTrue((REPO_ROOT / "CLAUDE.md").is_file())
        self.assertTrue((REPO_ROOT / "GEMINI.md").is_file())
        hardcoded_user_path = re.compile(
            r"(?:/Users/[A-Za-z0-9_.-]+|/home/[A-Za-z0-9_.-]+|[A-Za-z]:\\\\Users\\\\[A-Za-z0-9_.-]+)"
        )
        real_email_or_cal = re.compile(
            r"\b[A-Za-z0-9._%+-]+@(?:gmail\.com|group\.calendar\.google\.com|yahoo\.com|outlook\.com|icloud\.com)\b",
            re.IGNORECASE,
        )
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [
                d for d in dirs if d not in {".git", "__pycache__", ".venv", "venv", "scratch"}
            ]
            for fn in files:
                fp = Path(root) / fn
                rel = fp.relative_to(REPO_ROOT).as_posix()
                if rel == "tests/test_bootstrap_and_harness.py":
                    continue
                try:
                    txt = fp.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                m_path = hardcoded_user_path.search(txt)
                self.assertIsNone(
                    m_path,
                    msg=f"Hardcoded host user path '{m_path.group(0) if m_path else ''}' in {rel}",
                )
                m_mail = real_email_or_cal.search(txt)
                self.assertIsNone(
                    m_mail,
                    msg=f"Personal email/calendar literal '{m_mail.group(0) if m_mail else ''}' in {rel}",
                )
                if fn.lower().endswith((".md", ".txt", ".mdc")):
                    lint_label = rel if fn.lower().endswith(".md") else f"{rel}.md"
                    slop_err = lint_markdown_slop(lint_label, txt)
                    self.assertIsNone(slop_err, msg=f"{rel}: {slop_err}")
                if rel in (
                    ".agents/skills/council/references/personas.md",
                    ".agents/skills/iterate/references/critic_panels.md",
                ):
                    for ln in txt.splitlines():
                        if ln.startswith("# COUNCIL SEAT IDENTITY:"):
                            self.assertIsNotNone(
                                VALID_SEAT_IDENTITY_RE.match(ln),
                                msg=f"Invalid council seat header in {rel}: {ln}",
                            )


if __name__ == "__main__":
    unittest.main()
