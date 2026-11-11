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

    def test_entp_4w3_sosp_vs_entp_8w7_sxsp_differentiation(self) -> None:
        spec_4w3 = synthesize_dyadic_architecture(
            operator_mbti="ENTP",
            operator_enneagram="4w3",
            operator_instincts="so/sp",
            operator_name="PartnerA",
        )
        spec_8w7 = synthesize_dyadic_architecture(
            operator_mbti="ENTP",
            operator_enneagram="8w7",
            operator_instincts="sx/sp",
            operator_name="PartnerB",
        )
        self.assertEqual(spec_4w3["architect"]["mbti"], "INTJ")
        self.assertEqual(spec_8w7["architect"]["mbti"], "INTJ")
        self.assertEqual(spec_4w3["architect"]["enneagram"], "1w9 (with 5w4 Anchor)")
        self.assertEqual(spec_8w7["architect"]["enneagram"], "5w6 (with 1w9 Anchor)")
        self.assertIn("sx blind spot", spec_4w3["architect"]["bandwidth_defense_rule"])
        self.assertIn("sp operational baseline", spec_8w7["architect"]["bandwidth_defense_rule"])

    def test_diagnostic_grilling_scorer(self) -> None:
        self.assertEqual(len(DIAGNOSTIC_DILEMMAS), 6)
        res_entp = score_diagnostic_answers(
            {
                "D1": "Ne",
                "D2": "Fi",
                "D3": "Ne_loop",
                "D4": "4w3",
                "D5": "so/sp",
                "D6": "studio",
            }
        )
        self.assertEqual(res_entp["inferred_operator_mbti"], "ENFP")
        self.assertEqual(res_entp["inferred_operator_enneagram"], "4w3")
        self.assertEqual(res_entp["inferred_operator_instincts"], "so/sp")
        self.assertEqual(res_entp["proposed_architecture"]["architect"]["mbti"], "INTJ")

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
            "sample_hook_command",
        ):
            self.assertIn(key, info)
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
                    "4w3",
                    "--instincts",
                    "so/sp",
                    "--architect-name",
                    "Vera",
                    "--domains",
                    "Creative Direction, Music, Events",
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

            hooks_script = ws / ".agents" / "scripts" / "workspace_hooks.py"
            audit_script = ws / ".agents" / "scripts" / "audit_log.py"
            iterate_script = ws / ".agents" / "skills" / "iterate" / "scripts" / "iterate_stage.py"
            env = {**os.environ, "COARCHITECT_WORKSPACE_ROOT": str(ws)}

            # 1. Debug mode allows editing locked GEMINI.md; non-debug blocks shell mutation
            shell_block = subprocess.run(
                [sys.executable, str(hooks_script), "PreToolUse"],
                input=json.dumps(
                    {
                        "conversationId": "t1",
                        "lastUserInput": "append a line",
                        "toolCall": {
                            "name": "run_command",
                            "args": {"CommandLine": "echo hacked >> GEMINI.md"},
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
                                "Path": str(ws / "GEMINI.md"),
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


class TestStarterRepoSlopAndZeroPII(unittest.TestCase):
    def test_all_starter_markdown_and_zero_pii(self) -> None:
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
                if fn.lower().endswith(".md"):
                    slop_err = lint_markdown_slop(rel, txt)
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
