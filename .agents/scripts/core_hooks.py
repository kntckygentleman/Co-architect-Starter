#!/usr/bin/env python3
"""Cross-Platform Security, Provenance, Anti-Slop, & Subagent Tiering Kernel (`core_hooks.py`).

Zero external dependencies (Python 3.9+ standard library only).
Runs identically across macOS (`fcntl`), Linux/WSL (`fcntl`), and Windows (`msvcrt`).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone, tzinfo
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Iterator
from urllib.parse import urlparse

try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None  # type: ignore[assignment]

try:
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None  # type: ignore[assignment]

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore[assignment, misc]


GENESIS_HASH = "0" * 64
DANGLING_INCIDENT_TTL_SECONDS = 24 * 3600
MAX_EXTERNAL_LOOKUPS = 50
MAX_SECURITY_INCIDENTS = 25
SUBSTANTIVE_DATE_STAMP_DELTA_BYTES = 16
MAX_AUDIT_LOG_BYTES = int(os.environ.get("COARCHITECT_MAX_AUDIT_BYTES", str(10 * 1024 * 1024)))
MAX_BAK_SEGMENTS = int(os.environ.get("COARCHITECT_MAX_BAK_SEGMENTS", "5"))

ACCOUNTLESS_KORTEX_TOOLS = {"get_status", "list_accounts", "rate_kortex", "get_job"}
KORTEX_MUTATION_TOOLS = {
    "add_text_source",
    "add_url_source",
    "add_google_doc",
    "sync_google_docs",
    "create_notebook",
    "rename_notebook",
    "rename_source",
    "create_notebooklm_note",
    "update_notebooklm_note",
    "set_source_note",
    "set_source_highlight",
    "save_chat_to_note",
    "convert_note_to_source",
    "bulk",
    "batch_to_vault",
    "import_pipeline",
}

HIDDEN_UNICODE_RE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff\U000e0000-\U000e007f]"
)

STORED_INJECTION_RE = re.compile(
    r"(?:<\s*/?\s*(?:system|user_rules|claude_instruction|antigravity_instruction)\b"
    r"|<\s*RULE\s*\["
    r"|ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions"
    r"|disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions"
    r"|system\s+override\s*:)",
    re.IGNORECASE,
)

EXFIL_AND_SLOPSQUAT_CMD_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(curl|wget|nc|ncat|netcat|scp|sftp|ssh|rsync|dig|nslookup"
    r"|git\s+push|gh\s+(?:pr|issue|repo|gist|api)|gdrive\s+mutate\s+share"
    r"|python3?\s+-m\s+pip\s+install|pip3?\s+install|uv\s+pip\s+install|poetry\s+add"
    r"|npm\s+(?:install|i)\b|npx\b|pnpm\s+add|yarn\s+add|brew\s+install|cargo\s+install|go\s+install"
    r"|urllib\.request|http\.client|socket\.create_connection|requests\.(?:get|post|put|request)|httpx\.|fetch\s*\()",
    re.IGNORECASE,
)

ANY_DEBUG_MODE_RE = re.compile(
    r"(?:^|[\r\n>])\s*\[\s*[a-z0-9_-]+(?:\s+[a-z0-9_-]+)?\s+debug\s+mode\s*\]",
    re.IGNORECASE,
)

EPISTEMIC_CLEAR_CMD_RE = re.compile(
    r"\baudit_log\.py\b[^\n;|&]*\bepistemic\b[^\n;|&]*(--clear-taint|--ack-incidents)\b",
    re.IGNORECASE,
)

SHELL_SECRET_FILE_RE = re.compile(
    r"(?:mcp_config\.json|jetski-standalone-oauth-token|plugins/[^/\s'\"]+/auth\.json"
    r"|(?<![A-Za-z0-9_.-])\.env(?:\.(?!example\b|sample\b|template\b)[A-Za-z0-9_.-]+)?(?=$|[\s'\"`,|;&>)])"
    r"|/\.ssh/(?:id_[A-Za-z0-9_.-]+|authorized_keys)(?<!\.pub)(?=$|[\s'\"`,|;&>)]))",
    re.IGNORECASE,
)

HOST_CONFIG_LOCKED_REL_PATHS = (
    ".gemini/config/config.json",
    ".gemini/config/mcp_config.json",
    ".gemini/config/hooks.json",
)

EXOGENOUS_LOOKUP_TOOLS = {
    "mcp_gemini-api_gemini-api-docs_gemini_search_docs",
    "mcp_gemini-api_gemini-api-docs_gemini_get_doc",
    "search_web",
    "read_url_content",
    "search_marketplace",
}

TIER_1_SPEC_DOMAINS = (
    "docs.python.org",
    "peps.python.org",
    "packaging.python.org",
    "antigravity.google",
    "ai.google.dev",
    "aistudio.google.com",
    "cloud.google.com",
    "firebase.google.com",
    "developer.android.com",
    "developer.chrome.com",
    "web.dev",
    "w3.org",
    "rfc-editor.org",
    "ietf.org",
    "modelcontextprotocol.io",
    "developer.mozilla.org",
    "sqlite.org",
    "postgresql.org",
    "git-scm.com",
    "typescriptlang.org",
    "nodejs.org",
    "rust-lang.org",
    "go.dev",
)

TIER_2_PRACTITIONER_DOMAINS = (
    "github.com",
    "raw.githubusercontent.com",
    "arxiv.org",
    "dl.acm.org",
    "ieee.org",
    "usenix.org",
    "simonwillison.net",
    "eugeneyan.com",
    "hamel.dev",
    "shreyashankar.com",
    "lilianweng.github.io",
    "huyenchip.com",
    "anthropic.com",
    "openai.com",
    "deepmind.google",
    "stanford.edu",
    "berkeley.edu",
    "mit.edu",
    "llmstxt.org",
    "context7.com",
)

VALID_SUBAGENT_MODELS = ("flash_lite", "flash", "pro", "inherit")
FLASH_ONLY_SUBAGENT_TYPES = ("research", "image-generator")
OPERATOR_INHERIT_AUTH_RE = re.compile(
    r"(?:\[(?:CARBON_INHERIT|DEEP_COUNCIL|RELEASE_GATE)\]|(?<![A-Za-z0-9_-])--deep(?![A-Za-z0-9_-]))",
    re.IGNORECASE,
)
SUBAGENT_INHERIT_TAG_RE = re.compile(
    r"\[(?:CARBON_INHERIT|DEEP_COUNCIL|RELEASE_GATE)\]",
    re.IGNORECASE,
)

BANNED_SLOP_TERMS_RE = re.compile(
    r"\b(delve|delving|tapestry|testament|pivotal|crucial|underscore|underscores|"
    r"foster|fostering|streamline|seamless|paradigm|synergy|holistic|multifaceted|"
    r"robust|nuanced|empower|guardrails|hygiene|"
    r"overarching|flywheel|north star|connective tissue|load-bearing|sieve|unpack|"
    r"double-click|move the needle|symphonic|battle-tested)\b",
    re.IGNORECASE,
)

CONTRAST_FRAME_RE = re.compile(
    r"\b(?:it's not\s+[^.,;\n]+,\s*it's|isn't just about\s+[^.,;\n]+;\s*it's about|"
    r"less like\s+[^.,;\n]+,\s*and more like)\b",
    re.IGNORECASE,
)

PSEUDO_WEIGHT_RE = re.compile(r"\[WEIGHT:\s*[^\]]+\]", re.IGNORECASE)

SECRET_FLAG_REDACT_RE = re.compile(
    r"((?:--body|--text|--message|--note|--description|--summary|--title|--location|--comment|"
    r"--prompt|--attendees|--decision|--consequences|-m|"
    r"token|api_key|apikey|password|secret)\s*(?:=|\s+)\s*)(?:'[^']*'|\"[^\"]*\"|\S+)",
    re.IGNORECASE,
)
EMAIL_REDACT_RE = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
PHONE_REDACT_RE = re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\w)")
BENIGN_REDIRECT_RE = re.compile(r"(?:\d*>\s*/dev/null|\d*>\s*NUL|\d+>&\d+|>&\d+)", re.IGNORECASE)
SELF_OBSERVER_ANCHORED_RE = re.compile(
    r"^\s*(?:(?:\S*python[0-9.]*|py\s+-3)\s+)?(?:\S*[/\\])?(?:audit_log\.py\s+(?:query|summary|verify|changelog|record-adr|epistemic|tokens)|"
    r"iterate_stage\.py\s+(?:status|diff|bundle))(?:\s+[^;&|`$><\n]*)?\s*$",
    re.IGNORECASE,
)

VALID_SEAT_IDENTITY_RE = re.compile(
    r"^# COUNCIL SEAT IDENTITY:\s+([A-Z]+-(?:INTJ|INTP|ENTJ|ENTP|INFJ|INFP|ENFJ|ENFP|ISTJ|ISFJ|ESTJ|ESFJ|ISTP|ISFP|ESTP|ESFP))\b"
)

REQUIRED_PERSONA_MARKERS: tuple[str, ...] = (
    "**Operational Acronym:**",
    "**Role:**",
    "**Cognitive Stack:**",
    "**Anti-Roleplay Directive:**",
    "**Core Architecture Lock",
    "**Council Subagent Delegation Clause (Veil of Ignorance):**",
    "Observed Reality > Typology Heuristic",
)


@contextmanager
def exclusive_file_lock(file_obj: Any) -> Iterator[None]:
    """Cross-platform advisory file lock (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows)."""
    if _fcntl is not None:
        _fcntl.flock(file_obj.fileno(), _fcntl.LOCK_EX)
        try:
            yield
        finally:
            try:
                _fcntl.flock(file_obj.fileno(), _fcntl.LOCK_UN)
            except OSError:
                pass
    elif _msvcrt is not None:
        fd = file_obj.fileno()
        locked = False
        try:
            file_obj.seek(0)
            _msvcrt.locking(fd, _msvcrt.LK_LOCK, 1)
            locked = True
        except OSError:
            locked = False
        try:
            yield
        finally:
            if locked:
                try:
                    file_obj.seek(0)
                    _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
    else:
        yield


def resolve_local_tz(tz_name: str | None = None) -> tzinfo:
    if tz_name and ZoneInfo is not None and "/" in tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            pass
    try:
        return datetime.now().astimezone().tzinfo or timezone.utc
    except Exception:
        return timezone.utc


def now_local(tz_name: str | None = None) -> datetime:
    tz = resolve_local_tz(tz_name)
    ref_date = os.environ.get("COARCHITECT_REFERENCE_DATE", "").strip()
    if ref_date:
        try:
            dt = datetime.fromisoformat(ref_date)
            return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)
        except ValueError:
            pass
    return datetime.now(tz)


def resolve_workspace_root(caller_file: str | None = None) -> str:
    env_root = os.environ.get("COARCHITECT_WORKSPACE_ROOT", "").strip()
    if env_root:
        return os.path.abspath(env_root)
    for cand in (caller_file, __file__):
        if not cand:
            continue
        p_obj = Path(cand).resolve()
        if len(p_obj.parents) >= 3 and p_obj.parent.name == "scripts" and p_obj.parents[1].name == ".agents":
            return str(p_obj.parents[2])
    return str(Path(__file__).resolve().parents[2])


def _path_is_within(child_path: str, parent_dir: str) -> bool:
    try:
        c_norm = os.path.normcase(os.path.abspath(child_path))
        p_norm = os.path.normcase(os.path.abspath(parent_dir))
        return os.path.commonpath([c_norm, p_norm]) == p_norm
    except ValueError:
        return False


def lint_markdown_slop(target_path: str, text: str) -> str | None:
    if not target_path.lower().endswith(".md") or os.path.basename(target_path) == "human-voice.md":
        return None
    if "\u2014" in text or "\u2013" in text:
        return (
            "Anti-Slop Gate (human-voice.md): Em dash or en dash detected. "
            "Use commas, periods, colons, or parentheses instead."
        )
    if PSEUDO_WEIGHT_RE.search(text):
        return (
            "Anti-Slop Gate (human-voice.md): Unparsed '[WEIGHT: ...]' tag detected. "
            "Enforce invariants in Python hooks or state plain imperative rules."
        )
    if CONTRAST_FRAME_RE.search(text):
        return (
            "Anti-Slop Gate (human-voice.md): Negative-positive contrast frame detected. "
            "Skip the negation and state what the thing actually is."
        )
    match = BANNED_SLOP_TERMS_RE.search(text)
    if match:
        return (
            f"Anti-Slop Gate (human-voice.md): Banned AI filler/metaphor term "
            f"'{match.group(0)}' detected. Use plain, literal language."
        )
    return None


def lint_security_payload(
    target_label: str, text: str, *, check_stored_injection: bool = True
) -> str | None:
    if not text:
        return None
    if HIDDEN_UNICODE_RE.search(text):
        return (
            f"Security Gate (Invisible Unicode / Bidi Injection): Payload for '{target_label}' "
            "contains hidden zero-width, bidirectional override, or Unicode Tag characters "
            "(U+E0000..U+E007F). Strip hidden control characters before writing."
        )
    if check_stored_injection:
        inj_m = STORED_INJECTION_RE.search(text)
        if inj_m:
            return (
                f"Security Gate (Stored Prompt Injection): Payload for '{target_label}' contains "
                f"system-rule override tags or prompt-injection directives ('{inj_m.group(0)}'). "
                "Blocked from entering persistent state."
            )
    return None


def file_sha256_and_size(path: str) -> tuple[str | None, int | None]:
    if not path or not os.path.isfile(path):
        return None, None
    try:
        h = hashlib.sha256()
        size = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
                size += len(chunk)
        return h.hexdigest(), size
    except OSError:
        return None, None


def git_head_short(cwd: str) -> str:
    git_dir = os.path.join(cwd, ".git")
    head_file = os.path.join(git_dir, "HEAD")
    if not os.path.isfile(head_file):
        return "none"
    try:
        with open(head_file, "r", encoding="utf-8") as f:
            ref_line = f.read().strip()
        if not ref_line:
            return "uncommitted"
        if not ref_line.startswith("ref:"):
            return ref_line[:7]
        ref_rel = ref_line.split(":", 1)[1].strip()
        ref_path = os.path.join(git_dir, *ref_rel.split("/"))
        if os.path.isfile(ref_path):
            with open(ref_path, "r", encoding="utf-8") as rf:
                sha = rf.read().strip()
                return sha[:7] if sha else "uncommitted"
        packed_refs = os.path.join(git_dir, "packed-refs")
        if os.path.isfile(packed_refs):
            with open(packed_refs, "r", encoding="utf-8") as pf:
                for line in pf:
                    if line.startswith("#") or line.startswith("^"):
                        continue
                    parts = line.strip().split()
                    if len(parts) == 2 and parts[1] == ref_rel:
                        return parts[0][:7]
        return "uncommitted"
    except OSError:
        return "none"


def _extract_file_mutation_text(args: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("Content", "Replacement"):
        val = args.get(key)
        if isinstance(val, str) and val:
            chunks.append(val)
    rep_chunks = args.get("ReplacementChunks")
    if isinstance(rep_chunks, list):
        for item in rep_chunks:
            if isinstance(item, dict):
                rc = item.get("ReplacementContent") or item.get("Replacement")
                if isinstance(rc, str) and rc:
                    chunks.append(rc)
    return "\n".join(chunks)


def _classify_file_target(raw_path: str, workspace_root: str) -> str:
    norm = os.path.abspath(raw_path).replace("\\", "/")
    ws_norm = os.path.abspath(workspace_root).replace("\\", "/").rstrip("/")
    if norm.startswith(f"{ws_norm}/state/"):
        return "STATE_CACHE"
    if "/scratch/" in norm or "/.gemini/antigravity/brain/" in norm:
        return "ARTIFACT_STAGE"
    return "CODE_SYSTEM"


def _redact_command(cmd: str) -> str:
    cleaned = SECRET_FLAG_REDACT_RE.sub(r"\1[REDACTED]", cmd.strip())
    cleaned = EMAIL_REDACT_RE.sub("[EMAIL]", cleaned)
    cleaned = PHONE_REDACT_RE.sub("[PHONE]", cleaned)
    return cleaned[:240]


def _classify_command(cmd: str) -> str:
    low = cmd.strip().lower()
    if re.match(r"^(?:git\s+(?:status|log|diff|show|branch)|ls|pwd|dir|cat|head|tail|wc)\b", low):
        return "READ_QUERY"
    if re.search(r"\b(?:git\s+push|gh\s+(?:pr|repo|release))\b", low):
        return "EXTERNAL_ACTION"
    return "EXEC_CMD"


def _is_pure_self_observer_command(cmd: str) -> bool:
    return bool(SELF_OBSERVER_ANCHORED_RE.match(cmd.strip()))


def _shell_targets_locked_path(cmd: str, locked_rel_paths: tuple[str, ...]) -> str | None:
    norm_cmd = re.sub(r"\\\r?\n\s*", " ", cmd).replace("\\", "/")
    stripped = BENIGN_REDIRECT_RE.sub(" ", norm_cmd)
    scan_text = SECRET_FLAG_REDACT_RE.sub(r"\1REDACTED_ARG", stripped)
    is_inline_eval = bool(
        re.search(r"\b(?:python3?(?:\.\d+)?\s+-c|py\s+-3\s+-c|sh\s+-c|bash\s+-c|zsh\s+-c|pwsh\s+-c)\b|<<", scan_text)
    )
    for rel in locked_rel_paths:
        esc = re.escape(rel)
        base_esc = re.escape(os.path.basename(rel))
        pat = rf"(?:['\"]?[^\s;|&'\"]*/)?{esc}['\"]?"
        if re.search(rf"(?:>>?|(?<!-)\btee\b(?:\s+-a)?)\s*{pat}", scan_text):
            return rel
        if re.search(
            rf"\b(?:sed\s+-i|perl\s+-i|patch|rm|del|mv|move|cp|copy|dd|install|rsync|ln|truncate|Set-Content|Add-Content|Out-File|Remove-Item)\b[^;&|\n]*{pat}",
            scan_text,
            re.IGNORECASE,
        ):
            return rel
        if is_inline_eval and (rel in scan_text or os.path.basename(rel) in scan_text):
            if re.search(
                rf"(?:shutil\.copy\w*|os\.replace|os\.rename|os\.remove|os\.unlink|\.write_text|\.write_bytes|open\([^)]*['\"][rwa+]*[wa+]['\"])",
                scan_text,
            ) and re.search(rf"(?:{esc}|{base_esc})", scan_text):
                return rel
    return None


def _user_input_authorizes_command(user_input: str, token: str) -> bool:
    if not user_input or not token:
        return False
    pat = rf"(?<![A-Za-z0-9_.-]){re.escape(token)}(?![A-Za-z0-9_.-])"
    return bool(re.search(pat, user_input, re.IGNORECASE))


def _load_epistemic_manifest(manifest_path: str) -> dict[str, Any]:
    if not os.path.isfile(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as mf:
            data = json.load(mf)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _record_pre_hash(conv_id: str, step_idx: Any, target_path: str, cache_path: str) -> None:
    if not target_path:
        return
    sha_b, bytes_b = file_sha256_and_size(target_path)
    resolved = os.path.realpath(target_path)
    exact_key = f"{conv_id}:{step_idx}:{resolved}"
    path_key = f"path:{resolved}"
    payload_val = {
        "sha256_before": sha_b[:16] if sha_b else None,
        "bytes_before": bytes_b,
    }
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "a+", encoding="utf-8") as f:
            with exclusive_file_lock(f):
                f.seek(0)
                raw = f.read().strip()
                try:
                    data = json.loads(raw) if raw else {}
                    if not isinstance(data, dict):
                        data = {}
                except json.JSONDecodeError:
                    data = {}
                if len(data) > 64:
                    keys = list(data.keys())[-32:]
                    data = {k: data[k] for k in keys}
                data[exact_key] = payload_val
                data[path_key] = payload_val
                f.seek(0)
                f.truncate()
                f.write(json.dumps(data))
                f.flush()
    except Exception:
        pass


def _pop_pre_hash(conv_id: str, step_idx: Any, target_path: str, cache_path: str) -> tuple[str | None, int | None]:
    if not target_path or not os.path.isfile(cache_path):
        return None, None
    resolved = os.path.realpath(target_path)
    exact_key = f"{conv_id}:{step_idx}:{resolved}"
    path_key = f"path:{resolved}"
    try:
        with open(cache_path, "a+", encoding="utf-8") as f:
            with exclusive_file_lock(f):
                f.seek(0)
                raw = f.read().strip()
                if not raw:
                    return None, None
                try:
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        data = {}
                except json.JSONDecodeError:
                    f.seek(0)
                    f.truncate()
                    f.write("{}")
                    f.flush()
                    return None, None
                entry = data.pop(exact_key, None)
                fallback = data.pop(path_key, None)
                chosen = entry if entry is not None else fallback
                f.seek(0)
                f.truncate()
                f.write(json.dumps(data))
                f.flush()
                if isinstance(chosen, dict):
                    return chosen.get("sha256_before"), chosen.get("bytes_before")
    except Exception:
        pass
    return None, None


def compute_entry_hash(entry_without_hash: dict[str, Any]) -> str:
    canonical = json.dumps(entry_without_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_tail_hash_from_file(path: str) -> str | None:
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return None
    try:
        with open(path, "rb") as bf:
            bf.seek(0, os.SEEK_END)
            end_pos = bf.tell()
            read_len = min(end_pos, 16384)
            bf.seek(end_pos - read_len)
            tail_lines = bf.read(read_len).decode("utf-8", errors="replace").splitlines()
        for raw_ln in reversed(tail_lines):
            s_ln = raw_ln.strip()
            if not s_ln:
                continue
            obj = json.loads(s_ln)
            if isinstance(obj, dict) and isinstance(obj.get("entry_hash"), str):
                return obj["entry_hash"]
    except Exception:
        return None
    return None


def append_locked_audit_entry(
    log_path: str,
    entry_core: dict[str, Any],
    *,
    tz_name: str | None = None,
) -> dict[str, Any]:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    lock_file_path = f"{log_path}.lock"
    with open(lock_file_path, "a+", encoding="utf-8") as lock_fd:
        with exclusive_file_lock(lock_fd):
            if os.path.isfile(log_path) and os.path.getsize(log_path) >= MAX_AUDIT_LOG_BYTES:
                stamp = now_local(tz_name).strftime("%Y%m%dT%H%M%S")
                bak_path = f"{log_path}.{stamp}.bak"
                try:
                    os.replace(log_path, bak_path)
                    baks = sorted(glob.glob(f"{log_path}.*.bak"))
                    while len(baks) > MAX_BAK_SEGMENTS:
                        oldest = baks.pop(0)
                        try:
                            os.remove(oldest)
                        except OSError:
                            pass
                except OSError:
                    pass

            prev_hash = _read_tail_hash_from_file(log_path)
            if not prev_hash:
                baks = sorted(glob.glob(f"{log_path}.*.bak"))
                if baks:
                    prev_hash = _read_tail_hash_from_file(baks[-1])
            prev_hash = prev_hash or GENESIS_HASH

            record = dict(entry_core)
            record["prev_hash"] = prev_hash
            record["entry_hash"] = compute_entry_hash(record)
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(record, ensure_ascii=False) + "\n")
                lf.flush()
            return record


def apply_kortex_defaults(
    tool_args: dict[str, Any],
    kortex_tool: str,
    *,
    default_account: str = "",
    default_notebook_id: str = "",
) -> tuple[dict[str, Any], bool]:
    new_args = dict(tool_args)
    modified = False
    if default_account and kortex_tool not in ACCOUNTLESS_KORTEX_TOOLS and not new_args.get("account"):
        new_args["account"] = default_account
        modified = True
    if default_notebook_id and kortex_tool in ("get_source_content", "list_sources", "ask_question", "list_notes"):
        if not new_args.get("notebook_id"):
            new_args["notebook_id"] = default_notebook_id
            modified = True
    if kortex_tool == "ask_question" and "citation_format" not in new_args:
        new_args["citation_format"] = "none"
        modified = True
    return new_args, modified


def _host_matches_domain_list(host: str, domains: tuple[str, ...]) -> bool:
    h = host.lower().strip(".")
    return any(h == d or h.endswith(f".{d}") for d in domains)


def _classify_exogenous_lookup(tool_name: str, args: dict[str, Any]) -> tuple[str, str, str]:
    if tool_name.startswith("mcp_gemini-api_"):
        q = str(args.get("query") or args.get("chunk_id") or "")
        return "TIER_1_UPSTREAM_SPEC", "gemini-api-docs", q
    if tool_name == "search_marketplace":
        qs = args.get("queries") or []
        q_str = ", ".join(str(x) for x in qs[:3]) if isinstance(qs, list) else str(qs)
        return "TIER_1_UPSTREAM_SPEC", "antigravity-marketplace", q_str
    raw_url = str(args.get("Url") or args.get("url") or args.get("domain") or "")
    q = str(args.get("query") or raw_url or "")
    host = ""
    if raw_url:
        parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
        host = (parsed.hostname or "").lower()
    if host and _host_matches_domain_list(host, TIER_1_SPEC_DOMAINS):
        return "TIER_1_UPSTREAM_SPEC", host, q
    if host and _host_matches_domain_list(host, TIER_2_PRACTITIONER_DOMAINS):
        return "TIER_2_EMPIRICAL_PRACTITIONER", host, q
    return "TIER_3_UNVERIFIED_WEB", host or "web-search", q


_CLAUDE_SUBAGENT_MODEL_MAP: dict[str, str] = {
    "haiku": "flash",
    "claude-haiku": "flash",
    "fast": "flash_lite",
    "flash": "flash",
    "flash_lite": "flash_lite",
    "sonnet": "pro",
    "claude-sonnet": "pro",
    "pro": "pro",
    "opus": "inherit",
    "claude-opus": "inherit",
    "inherit": "inherit",
}


def normalize_hook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Antigravity (`toolCall`) and Claude Code (`tool_name`/`tool_input`) payloads."""
    if not isinstance(payload, dict):
        return {"_hook_platform": "antigravity", "toolCall": {}}
    out = dict(payload)
    if "toolCall" in out and isinstance(out["toolCall"], dict):
        out.setdefault("_hook_platform", "antigravity")
        return out

    is_claude = any(k in out for k in ("tool_name", "hook_event_name", "session_id"))
    out.setdefault("_hook_platform", "claude" if is_claude else "antigravity")

    if "conversationId" not in out and "session_id" in out:
        out["conversationId"] = out.get("session_id")
    if "lastUserInput" not in out:
        for key in ("prompt", "last_user_message", "user_prompt"):
            if key in out and out[key] is not None:
                out["lastUserInput"] = out[key]
                break
    if "toolResponse" not in out and "tool_response" in out:
        out["toolResponse"] = out.get("tool_response")

    raw_tool = str(out.get("tool_name") or "").strip()
    if not raw_tool:
        out.setdefault("toolCall", {})
        return out

    ti = out.get("tool_input")
    if not isinstance(ti, dict):
        ti = {}

    if raw_tool == "Write":
        tc: dict[str, Any] = {
            "name": "write_file",
            "args": {
                "Path": str(ti.get("file_path") or ti.get("path") or ""),
                "Content": str(ti.get("content") or ""),
            },
        }
    elif raw_tool == "Edit":
        tc = {
            "name": "edit_file",
            "args": {
                "Path": str(ti.get("file_path") or ti.get("path") or ""),
                "Target": str(ti.get("old_string") or ""),
                "Replacement": str(ti.get("new_string") or ""),
            },
        }
    elif raw_tool == "MultiEdit":
        edits = ti.get("edits") if isinstance(ti.get("edits"), list) else []
        targets: list[str] = []
        replacements: list[str] = []
        for item in edits:
            if isinstance(item, dict):
                if isinstance(item.get("old_string"), str):
                    targets.append(item["old_string"])
                if isinstance(item.get("new_string"), str):
                    replacements.append(item["new_string"])
        tc = {
            "name": "edit_file",
            "args": {
                "Path": str(ti.get("file_path") or ti.get("path") or ""),
                "Target": "\n".join(targets),
                "Replacement": "\n".join(replacements),
            },
        }
    elif raw_tool == "Read":
        tc = {
            "name": "read_file",
            "args": {"Path": str(ti.get("file_path") or ti.get("path") or "")},
        }
    elif raw_tool == "Bash":
        tc = {
            "name": "run_command",
            "args": {
                "CommandLine": str(ti.get("command") or ti.get("cmd") or ""),
                "toolSummary": str(ti.get("description") or ""),
            },
        }
    elif raw_tool in ("Task", "Agent"):
        sub_type = str(ti.get("subagent_type") or ti.get("type") or ti.get("name") or "worker")
        has_explicit_model = "model" in ti or "Model" in ti
        raw_model = str(ti.get("model") or ti.get("Model") or "").strip()
        if not has_explicit_model:
            norm_model = (
                "flash"
                if (sub_type.lower() in FLASH_ONLY_SUBAGENT_TYPES or sub_type.lower().endswith("-worker"))
                else "pro"
            )
        else:
            norm_model = _CLAUDE_SUBAGENT_MODEL_MAP.get(raw_model.lower(), raw_model)
        tc = {
            "name": "invoke_subagent",
            "args": {
                "TypeName": sub_type,
                "Role": str(ti.get("description") or ti.get("name") or ""),
                "Prompt": str(ti.get("prompt") or ""),
                "Model": norm_model,
            },
        }
    elif raw_tool == "WebSearch":
        tc = {"name": "search_web", "args": {"query": str(ti.get("query") or "")}}
    elif raw_tool == "WebFetch":
        url_val = str(ti.get("url") or "")
        tc = {
            "name": "read_url_content",
            "args": {"Url": url_val, "url": url_val, "query": str(ti.get("prompt") or "")},
        }
    elif raw_tool.startswith("mcp__") and raw_tool.count("__") >= 2:
        _, srv_name, mcp_tool_name = raw_tool.split("__", 2)
        tc = {
            "name": "call_mcp_tool",
            "args": {"ServerName": srv_name, "ToolName": mcp_tool_name, "Arguments": dict(ti)},
        }
    else:
        tc = {"name": raw_tool, "args": dict(ti)}

    out["toolCall"] = tc
    return out


def evaluate_base_pre_tool_use(
    payload: dict[str, Any],
    *,
    workspace_root: str,
    locked_paths: set[str],
    locked_rel_paths: tuple[str, ...],
    debug_phrase: str,
    default_kortex_account: str = "",
    default_notebook_id: str = "",
) -> dict[str, Any]:
    payload = normalize_hook_payload(payload)
    tool_call = payload.get("toolCall") or {}
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args") or {}
    last_user_input = (payload.get("lastUserInput") or "").lstrip()
    in_debug_mode = bool(debug_phrase) and last_user_input.lower().startswith(debug_phrase.lower())
    user_input_sha = (
        hashlib.sha256(last_user_input.encode("utf-8")).hexdigest()[:16] if last_user_input else "empty"
    )
    conv_id = str(payload.get("conversationId") or "local")[:12]
    step_idx = payload.get("stepIdx")
    manifest_path = os.path.join(workspace_root, "state", "epistemic_manifest.json")
    pre_hash_path = os.path.join(workspace_root, "state", ".pre_tool_hashes.json")

    if tool_name in ("edit_file", "write_file"):
        target_path = str(args.get("Path") or "")
        if target_path:
            abs_target = os.path.abspath(target_path)
            resolved = os.path.realpath(target_path)
            gemini_cfg_abs = os.path.abspath(os.path.expanduser("~/.gemini/config"))
            gemini_cfg_real = os.path.realpath(gemini_cfg_abs)
            if (
                _path_is_within(abs_target, gemini_cfg_abs)
                or _path_is_within(resolved, gemini_cfg_real)
            ) and not in_debug_mode:
                return {
                    "decision": "deny",
                    "reason": (
                        f"Host Config Lock: Direct file mutations inside '~/.gemini/config' are "
                        f"blocked unless '{debug_phrase}' is active."
                    ),
                }
            norm_resolved = os.path.normcase(resolved)
            if norm_resolved in locked_paths and not in_debug_mode:
                return {
                    "decision": "deny",
                    "reason": (
                        f"Core Architecture Lock: '{os.path.basename(target_path)}' is locked "
                        f"during normal operation. Start your prompt with '{debug_phrase}' to "
                        "modify core identity, rule, skill, or hook files."
                    ),
                }
            body_text = _extract_file_mutation_text(args)
            is_state_cache = _classify_file_target(target_path, workspace_root) == "STATE_CACHE"
            sec_err = lint_security_payload(
                os.path.basename(target_path),
                body_text,
                check_stored_injection=is_state_cache,
            )
            if sec_err:
                return {"decision": "deny", "reason": sec_err}
            slop_err = lint_markdown_slop(target_path, body_text)
            if slop_err:
                return {"decision": "deny", "reason": slop_err}
            _record_pre_hash(conv_id, step_idx, target_path, cache_path=pre_hash_path)

    if tool_name == "run_command":
        cmd_line = str(args.get("CommandLine") or "")
        secret_m = SHELL_SECRET_FILE_RE.search(cmd_line)
        if secret_m and not in_debug_mode:
            return {
                "decision": "deny",
                "reason": (
                    f"Secret Isolation Gate (Shell Guard): Command references protected credential "
                    f"file '{secret_m.group(0).strip()}'. Direct shell inspection of host tokens and "
                    f"'.env' files is blocked unless '{debug_phrase}' is active."
                ),
            }
        host_cfg_hit = (
            _shell_targets_locked_path(cmd_line, HOST_CONFIG_LOCKED_REL_PATHS)
            if ".gemini/config" in cmd_line.replace("\\", "/")
            else None
        )
        if host_cfg_hit and not in_debug_mode:
            return {
                "decision": "deny",
                "reason": (
                    f"Host Config Lock (Shell Guard): Command appears to mutate '{host_cfg_hit}' "
                    f"inside '~/.gemini/config'. Requires '{debug_phrase}'."
                ),
            }
        clear_m = EPISTEMIC_CLEAR_CMD_RE.search(cmd_line)
        if clear_m:
            flag_tok = clear_m.group(1)
            if not _user_input_authorizes_command(last_user_input, flag_tok):
                return {
                    "decision": "deny",
                    "reason": (
                        f"Epistemic Integrity Gate: '{flag_tok}' resets security/taint telemetry and "
                        "cannot be self-executed unless the operator explicitly includes "
                        f"'{flag_tok}' in the current prompt."
                    ),
                }
        locked_hit = _shell_targets_locked_path(cmd_line, locked_rel_paths)
        if locked_hit and not in_debug_mode:
            return {
                "decision": "deny",
                "reason": (
                    f"Core Architecture Lock (Shell Guard): Command appears to mutate locked file "
                    f"'{locked_hit}'. Start your prompt with '{debug_phrase}' to modify locked files."
                ),
            }
        exfil_m = EXFIL_AND_SLOPSQUAT_CMD_RE.search(cmd_line)
        if exfil_m:
            m_data = _load_epistemic_manifest(manifest_path)
            c_meta = (m_data.get("conv_reads") or {}).get(conv_id) or {}
            taint_list = c_meta.get("taint_sources") or []
            taint_turn_sha = c_meta.get("taint_user_input_sha256")
            has_sticky_injection = "INJECTION_DETECTED_IN_RESPONSE" in taint_list
            active_taint = (
                taint_list
                if (has_sticky_injection or not taint_turn_sha or taint_turn_sha == user_input_sha)
                else []
            )
            matched_bin = re.sub(r"\s+", " ", exfil_m.group(1).strip().lower()).rstrip("(").strip()
            if active_taint and not _user_input_authorizes_command(last_user_input, matched_bin):
                return {
                    "decision": "deny",
                    "reason": (
                        f"CaMeL Taint Gate: Conversation has ingested untrusted external content "
                        f"({', '.join(active_taint)}). Outbound network or package-install token "
                        f"'{matched_bin}' is blocked unless explicitly requested in the operator's "
                        "current prompt or cleared via '--clear-taint'."
                    ),
                }

    if tool_name in ("search_web", "read_url_content"):
        m_data_web = _load_epistemic_manifest(manifest_path)
        c_meta_web = (m_data_web.get("conv_reads") or {}).get(conv_id) or {}
        taint_list_web = c_meta_web.get("taint_sources") or []
        if "INJECTION_DETECTED_IN_RESPONSE" in taint_list_web and not in_debug_mode:
            return {
                "decision": "deny",
                "reason": (
                    "CaMeL Sticky Injection Gate: Active prompt-injection incident recorded. "
                    "Outbound web fetches are blocked until operator clearance ('--clear-taint')."
                ),
            }

    if tool_name == "call_mcp_tool" and args.get("ServerName") == "kortex":
        kortex_tool = str(args.get("ToolName") or "")
        tool_args = dict(args.get("Arguments") or {})
        if kortex_tool in KORTEX_MUTATION_TOOLS:
            sec_err = lint_security_payload(f"kortex.{kortex_tool}", json.dumps(tool_args, ensure_ascii=False))
            if sec_err:
                return {"decision": "deny", "reason": sec_err}
        new_args, modified = apply_kortex_defaults(
            tool_args,
            kortex_tool,
            default_account=default_kortex_account,
            default_notebook_id=default_notebook_id,
        )
        if modified:
            return {"decision": "allow", "overwrite": {"Arguments": new_args}}

    if tool_name == "send_message":
        msg_body = str(args.get("Message") or "")
        if ANY_DEBUG_MODE_RE.search(msg_body) and not in_debug_mode:
            return {
                "decision": "deny",
                "reason": (
                    "Subagent Privilege-Escalation Gate: 'send_message' cannot inject a "
                    "'[... Debug Mode]' header when the parent session is not in debug mode."
                ),
            }

    if tool_name == "invoke_subagent":
        sub_model = str(args.get("Model") or "").strip()
        sub_type = str(args.get("TypeName") or "").strip().lower()
        sub_role = str(args.get("Role") or "").strip()
        sub_prompt = str(args.get("Prompt") or "").strip()
        sub_combined = f"{sub_type} {sub_role} {sub_prompt}"
        if (ANY_DEBUG_MODE_RE.search(sub_prompt) or ANY_DEBUG_MODE_RE.search(sub_role)) and not in_debug_mode:
            return {
                "decision": "deny",
                "reason": (
                    "Subagent Privilege-Escalation Gate: 'invoke_subagent' cannot inject a "
                    "'[... Debug Mode]' header when the parent session is not in debug mode."
                ),
            }
        if sub_model not in VALID_SUBAGENT_MODELS:
            return {
                "decision": "deny",
                "reason": (
                    f"Subagent Model Tiering Gate: 'Model' must be explicitly set to one of "
                    f"{list(VALID_SUBAGENT_MODELS)} (received {sub_model!r}). 'hydrogen', "
                    "'orchestrator', 'carbon', and 'argon' are Parent UI / API models; pass "
                    "'flash' for workers and Round 2+ diffs, or 'pro' for Round 1 /iterate "
                    "panels and /council."
                ),
            }
        if (
            sub_type in FLASH_ONLY_SUBAGENT_TYPES
            or sub_type.endswith("-worker")
            or "[ROUND_2_DIFF]" in sub_combined
        ) and sub_model not in ("flash", "flash_lite"):
            return {
                "decision": "deny",
                "reason": (
                    f"Subagent Model Tiering Gate: '{sub_type or sub_role}' must use "
                    "Model='flash' (or 'flash_lite') to protect shared frontier model quota."
                ),
            }
        if sub_model == "inherit":
            operator_authorized = bool(OPERATOR_INHERIT_AUTH_RE.search(last_user_input))
            subagent_tagged = bool(SUBAGENT_INHERIT_TAG_RE.search(sub_combined))
            if not (operator_authorized and subagent_tagged):
                return {
                    "decision": "deny",
                    "reason": (
                        "Subagent Model Tiering Gate: Model='inherit' clones the active Parent UI "
                        "model (including Carbon or Orchestrator (Carbon) planning turns) across "
                        "spawned subagents and can drain shared frontier quota. Default to "
                        "Model='pro' for /council and Round 1 /iterate, or explicitly include "
                        "'--deep', '[DEEP_COUNCIL]', '[RELEASE_GATE]', or '[CARBON_INHERIT]' in "
                        "both the operator prompt and subagent prompt."
                    ),
                }

    return {"decision": "allow"}


def _atomic_stamp_state_cache_date(path: str, today_iso: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
        updated = re.sub(
            r"(\*\*Last Updated:\*\*\s*)\d{4}-\d{2}-\d{2}",
            rf"\g<1>{today_iso}",
            txt,
            count=1,
        )
        if updated != txt:
            tmp_p = f"{path}.tmp"
            with open(tmp_p, "w", encoding="utf-8") as tf:
                tf.write(updated)
            os.replace(tmp_p, path)
    except OSError:
        pass


def _update_epistemic_manifest(
    *,
    manifest_path: str,
    ts_iso: str,
    conv_id: str,
    local_state_mutated: bool = False,
    external_lookup: dict[str, Any] | None = None,
    runtime_conformance_ran: bool = False,
    taint_source: str | None = None,
    user_input_sha256: str | None = None,
    security_incident: dict[str, Any] | None = None,
) -> None:
    if not (
        local_state_mutated
        or external_lookup
        or runtime_conformance_ran
        or taint_source
        or security_incident
    ):
        return
    try:
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "a+", encoding="utf-8") as mf:
            with exclusive_file_lock(mf):
                mf.seek(0)
                raw = mf.read().strip()
                try:
                    data = json.loads(raw) if raw else {}
                    if not isinstance(data, dict):
                        data = {}
                except json.JSONDecodeError:
                    data = {}

                if local_state_mutated:
                    data["latest_local_state_mut_ts"] = ts_iso

                if external_lookup or runtime_conformance_ran or taint_source:
                    conv_map = data.setdefault("conv_reads", {})
                    if len(conv_map) > 32:
                        keep = list(conv_map.keys())[-16:]
                        data["conv_reads"] = {k: conv_map[k] for k in keep}
                        conv_map = data["conv_reads"]
                    c_entry = conv_map.setdefault(
                        conv_id,
                        {
                            "external_tiers": [],
                            "taint_sources": [],
                            "runtime_conformance": False,
                        },
                    )
                    if external_lookup and external_lookup.get("tier"):
                        tiers = set(c_entry.get("external_tiers") or [])
                        tiers.add(str(external_lookup["tier"]))
                        c_entry["external_tiers"] = sorted(tiers)
                    if taint_source:
                        prev_sha = c_entry.get("taint_user_input_sha256")
                        cur_ts = set(c_entry.get("taint_sources") or [])
                        if user_input_sha256 and prev_sha and prev_sha != user_input_sha256:
                            cur_ts = {t for t in cur_ts if t == "INJECTION_DETECTED_IN_RESPONSE"}
                        cur_ts.add(taint_source)
                        c_entry["taint_sources"] = sorted(cur_ts)
                        if user_input_sha256:
                            c_entry["taint_user_input_sha256"] = user_input_sha256
                    if runtime_conformance_ran:
                        c_entry["runtime_conformance"] = True

                if external_lookup:
                    ext_list = data.setdefault("external_lookups", [])
                    if not isinstance(ext_list, list):
                        ext_list = []
                    ext_list.append(external_lookup)
                    data["external_lookups"] = ext_list[-MAX_EXTERNAL_LOOKUPS:]

                if security_incident:
                    sec_list = data.setdefault("security_incidents", [])
                    if not isinstance(sec_list, list):
                        sec_list = []
                    sec_list.append(security_incident)
                    data["security_incidents"] = sec_list[-MAX_SECURITY_INCIDENTS:]

                data["updated_at"] = ts_iso
                mf.seek(0)
                mf.truncate()
                mf.write(json.dumps(data, indent=2) + "\n")
                mf.flush()
    except Exception:
        pass


def handle_post_tool_use(
    payload: dict[str, Any],
    *,
    workspace_root: str,
    tz_name: str | None = None,
) -> dict[str, Any]:
    payload = normalize_hook_payload(payload)
    tool_call = payload.get("toolCall") or {}
    tool_name = tool_call.get("name", "")
    if not tool_name:
        return {}

    audit_log_path = os.path.join(workspace_root, "state", "audit_log.jsonl")
    manifest_path = os.path.join(workspace_root, "state", "epistemic_manifest.json")
    pre_hash_path = os.path.join(workspace_root, "state", ".pre_tool_hashes.json")
    err_log_path = os.path.join(workspace_root, "state", "hook_errors.log")

    args = tool_call.get("args") or {}
    error_str = str(payload.get("error") or payload.get("toolError") or "").strip()
    resp_probe = payload.get("toolResponse") or payload.get("response") or payload.get("result") or payload.get("output")
    if not error_str and isinstance(resp_probe, dict):
        if resp_probe.get("isError") is True or resp_probe.get("error"):
            error_str = str(resp_probe.get("error") or resp_probe.get("content") or "tool error")[:160]
        elif resp_probe.get("exitCode") not in (None, 0) or resp_probe.get("returnCode") not in (None, 0):
            ec = resp_probe.get("exitCode") if resp_probe.get("exitCode") is not None else resp_probe.get("returnCode")
            error_str = f"exit code {ec}"
    status = f"ERROR: {error_str[:160]}" if error_str else "OK"

    last_user_input = (payload.get("lastUserInput") or "").lstrip()
    user_input_sha = (
        hashlib.sha256(last_user_input.encode("utf-8")).hexdigest()[:16] if last_user_input else "empty"
    )
    conv_id = str(payload.get("conversationId") or "local")[:12]
    step_idx = payload.get("stepIdx")
    now_dt = now_local(tz_name)
    ts_iso = now_dt.isoformat(timespec="seconds")

    category = "EXEC_CMD"
    target = tool_name
    summary = ""
    sha256_before: str | None = None
    bytes_before: int | None = None
    sha256_after: str | None = None
    bytes_after: int | None = None
    mutated: bool | None = None

    if tool_name in ("edit_file", "write_file"):
        raw_path = str(args.get("Path") or "")
        target = raw_path
        category = _classify_file_target(raw_path, workspace_root)
        sha256_before, bytes_before = _pop_pre_hash(conv_id, step_idx, raw_path, cache_path=pre_hash_path)
        sha_full, bytes_after = file_sha256_and_size(raw_path)
        sha256_after = sha_full[:16] if sha_full else None
        mutated = (sha256_before != sha256_after) if sha256_after is not None else False
        delta_b = (bytes_after or 0) - (bytes_before or 0)
        if (
            mutated
            and not error_str
            and category == "STATE_CACHE"
            and raw_path.endswith(".md")
            and os.path.isfile(raw_path)
        ):
            if bytes_before is None or abs(delta_b) >= SUBSTANTIVE_DATE_STAMP_DELTA_BYTES:
                _atomic_stamp_state_cache_date(raw_path, now_dt.date().isoformat())
                sha_full, bytes_after = file_sha256_and_size(raw_path)
                sha256_after = sha_full[:16] if sha_full else None
                delta_b = (bytes_after or 0) - (bytes_before or 0)
            _update_epistemic_manifest(
                manifest_path=manifest_path,
                ts_iso=ts_iso,
                conv_id=conv_id,
                local_state_mutated=True,
            )
        summary = f"{tool_name} ({bytes_after or 0}B, delta={delta_b:+d}B, mutated={mutated})"
    elif tool_name == "run_command":
        cmd_line = str(args.get("CommandLine") or "")
        if _is_pure_self_observer_command(cmd_line) and not error_str:
            return {}
        category = _classify_command(cmd_line)
        target = _redact_command(cmd_line)
        summary = str(args.get("toolSummary") or "").strip()
        if not error_str and category == "EXEC_CMD":
            _update_epistemic_manifest(
                manifest_path=manifest_path,
                ts_iso=ts_iso,
                conv_id=conv_id,
                runtime_conformance_ran=True,
            )
    elif tool_name in EXOGENOUS_LOOKUP_TOOLS:
        category = "EXTERNAL_LOOKUP"
        mutated = False
        tier, src_label, q_sum = _classify_exogenous_lookup(tool_name, args)
        target = f"{tool_name}:{src_label}"
        raw_resp = ""
        if resp_probe is not None:
            try:
                raw_resp = resp_probe if isinstance(resp_probe, str) else json.dumps(resp_probe, ensure_ascii=False)
            except Exception:
                raw_resp = ""
        if raw_resp:
            enc = raw_resp.encode("utf-8", errors="replace")
            sha256_after = hashlib.sha256(enc).hexdigest()[:16]
            bytes_after = len(enc)
        summary = f"[{tier}] {q_sum}"[:220]
        if not error_str:
            sec_err = lint_security_payload(target, raw_resp, check_stored_injection=True) if raw_resp else None
            sec_inc = (
                {"ts": ts_iso, "conv_id": conv_id, "source": target, "alert": sec_err}
                if sec_err
                else None
            )
            taint_src = (
                "INJECTION_DETECTED_IN_RESPONSE"
                if sec_inc
                else (f"WEB:{src_label}" if tier == "TIER_3_UNVERIFIED_WEB" else None)
            )
            _update_epistemic_manifest(
                manifest_path=manifest_path,
                ts_iso=ts_iso,
                conv_id=conv_id,
                external_lookup={
                    "ts": ts_iso,
                    "conv_id": conv_id,
                    "tool": tool_name,
                    "tier": tier,
                    "source": src_label,
                    "query": q_sum[:140],
                    "sha256": sha256_after,
                },
                taint_source=taint_src,
                user_input_sha256=user_input_sha if taint_src else None,
                security_incident=sec_inc,
            )
    elif tool_name == "invoke_subagent":
        sub_type = str(args.get("TypeName") or "")
        sub_role = str(args.get("Role") or "")
        sub_model = str(args.get("Model") or "inherit").strip() or "inherit"
        category = "SUBAGENT"
        target = sub_type
        summary = f"{sub_role} [model={sub_model}]".strip()
    elif tool_name == "read_file":
        raw_path = str(args.get("Path") or "")
        category = "READ_QUERY"
        mutated = False
        target = raw_path
        summary = f"read_file ({os.path.basename(raw_path) or raw_path})"
    elif tool_name == "call_mcp_tool":
        server = str(args.get("ServerName") or "")
        mcp_tool = str(args.get("ToolName") or "")
        category = "VAULT_SYNC" if (server == "kortex" and mcp_tool in KORTEX_MUTATION_TOOLS) else "READ_QUERY"
        mutated = category == "VAULT_SYNC"
        target = f"{server}.{mcp_tool}"
        summary = f"mcp:{server}.{mcp_tool}"

    try:
        entry_core = {
            "ts": ts_iso,
            "conv_id": conv_id,
            "step_idx": step_idx,
            "category": category,
            "tool": tool_name,
            "target": target,
            "summary": summary,
            "status": status,
            "sha256_before": sha256_before,
            "sha256_after": sha256_after,
            "bytes_after": bytes_after,
            "mutated": mutated,
            "git_head": git_head_short(workspace_root),
        }
        append_locked_audit_entry(audit_log_path, entry_core, tz_name=tz_name)
    except Exception as exc:
        try:
            os.makedirs(os.path.dirname(err_log_path), exist_ok=True)
            with open(err_log_path, "a", encoding="utf-8") as ef:
                ef.write(f"[{ts_iso}] PostToolUse error: {exc}\n")
        except OSError:
            pass

    return {}


def check_session_start_anomalies(
    workspace_root: str,
    *,
    tz_name: str | None = None,
) -> list[str]:
    alerts: list[str] = []
    now_val = now_local(tz_name)
    cutoff_24h = now_val - timedelta(seconds=DANGLING_INCIDENT_TTL_SECONDS)

    m_data = _load_epistemic_manifest(os.path.join(workspace_root, "state", "epistemic_manifest.json"))
    for sec_inc in (m_data.get("security_incidents") or [])[-5:]:
        if isinstance(sec_inc, dict) and not sec_inc.get("acknowledged"):
            try:
                inc_dt = datetime.fromisoformat(str(sec_inc.get("ts") or ""))
                if inc_dt >= cutoff_24h:
                    alerts.append(
                        f"Prompt-injection / hidden-Unicode payload detected in {sec_inc.get('source')} ({str(sec_inc.get('ts'))[:16]})."
                    )
            except ValueError:
                pass

    for err_rel in ("state/hook_errors.log", "state/audit_corrupt.jsonl"):
        err_p = os.path.join(workspace_root, *err_rel.split("/"))
        if os.path.isfile(err_p) and os.path.getsize(err_p) > 0:
            alerts.append(f"System anomaly log non-empty: {err_rel} ({os.path.getsize(err_p)}B).")

    sys_p = os.path.join(workspace_root, "SYSTEM_PROMPT.md")
    if os.path.isfile(sys_p):
        sha_s, _ = file_sha256_and_size(sys_p)
        for mirror_name in ("AGENTS.md", "GEMINI.md", "CLAUDE.md"):
            m_p = os.path.join(workspace_root, mirror_name)
            if os.path.isfile(m_p):
                sha_m, _ = file_sha256_and_size(m_p)
                if sha_s and sha_m and sha_s != sha_m:
                    alerts.append(f"SYSTEM_PROMPT.md and {mirror_name} SHA-256 mismatch detected.")

    return alerts


def audit_state_files(
    state_files_to_audit: list[tuple[str, str, int, int, int | None]],
    *,
    workspace_root: str,
    alert_prefix: str = "STATE AUDIT ALERT",
    tz_name: str | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    now_dt = now_local(tz_name)
    today = now_dt.date()

    for label, path, max_lines, max_bytes, max_stale_days in state_files_to_audit:
        if not os.path.exists(path):
            warnings.append(f"Missing core state file: {label}")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                content = "".join(lines)
            byte_size = len(content.encode("utf-8"))
        except OSError:
            continue

        if len(lines) > max_lines:
            warnings.append(f"{label} is at {len(lines)} lines (exceeds {max_lines}-line cap; compact immediately).")
        if max_bytes and byte_size > max_bytes:
            warnings.append(f"{label} is at {byte_size} bytes (exceeds {max_bytes}-byte cap; compact immediately).")

        match = re.search(
            r"(?:\*\*Last Updated:\*\*|\*\*Last Synced:\*\*|last_updated:)\s*(\d{4}-\d{2}-\d{2})",
            content,
            re.IGNORECASE,
        )
        if match:
            if max_stale_days is not None:
                try:
                    updated_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                    delta_days = (today - updated_date).days
                    if delta_days > max_stale_days:
                        warnings.append(
                            f"{label} last_updated is {match.group(1)} ({delta_days} days old; confirm status with operator)."
                        )
                except ValueError:
                    pass
        elif max_stale_days is not None:
            warnings.append(f"{label} is missing a visible Last Updated date.")

    warnings.extend(check_session_start_anomalies(workspace_root, tz_name=tz_name))
    if not warnings:
        return {}
    joined = " | ".join(warnings)
    return {"additionalContext": f"{alert_prefix}: {joined}"}


def dispatch_hook_cli(
    *,
    workspace_root: str,
    pre_handler: Callable[[dict[str, Any]], dict[str, Any]],
    post_handler: Callable[[dict[str, Any]], dict[str, Any]],
    session_handler: Callable[[dict[str, Any]], dict[str, Any]],
    tz_name: str | None = None,
) -> None:
    event_name = sys.argv[1] if len(sys.argv) > 1 else ""
    raw_stdin = ""
    if not sys.stdin.isatty():
        try:
            raw_stdin = sys.stdin.read()
        except Exception:
            raw_stdin = ""
    raw_payload: dict[str, Any] = {}
    if raw_stdin.strip():
        try:
            parsed = json.loads(raw_stdin)
            if isinstance(parsed, dict):
                raw_payload = parsed
        except json.JSONDecodeError:
            raw_payload = {}

    payload = normalize_hook_payload(raw_payload)
    is_claude = payload.get("_hook_platform") == "claude"
    exit_code = 0

    audit_log_path = os.path.join(workspace_root, "state", "audit_log.jsonl")
    if event_name == "SessionStart":
        out = session_handler(payload)
        if is_claude and isinstance(out, dict) and out.get("additionalContext"):
            out = {
                **out,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": out["additionalContext"],
                },
            }
    elif event_name == "PreToolUse":
        out = pre_handler(payload)
        if out.get("decision") == "deny":
            try:
                tc = payload.get("toolCall") or {}
                t_name = str(tc.get("name") or "unknown")
                t_args = tc.get("args") or {}
                raw_tgt = str(t_args.get("Path") or t_args.get("CommandLine") or t_name)
                append_locked_audit_entry(
                    audit_log_path,
                    {
                        "ts": now_local(tz_name).isoformat(timespec="seconds"),
                        "conv_id": str(payload.get("conversationId") or "local")[:12],
                        "step_idx": payload.get("stepIdx"),
                        "category": "PRE_TOOL_BLOCK",
                        "tool": t_name,
                        "target": _redact_command(raw_tgt),
                        "summary": str(out.get("reason") or "Denied")[:200],
                        "status": "BLOCKED",
                        "sha256_before": None,
                        "sha256_after": None,
                        "bytes_after": None,
                        "mutated": False,
                        "git_head": git_head_short(workspace_root),
                    },
                    tz_name=tz_name,
                )
            except Exception:
                pass
            if is_claude:
                reason_txt = str(out.get("reason") or "Blocked by workspace policy.")
                out = {
                    **out,
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason_txt,
                    },
                }
                sys.stderr.write(reason_txt + "\n")
                sys.stderr.flush()
                exit_code = 2
        elif is_claude and isinstance(out, dict) and out.get("decision") == "allow":
            out = {
                **out,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                },
            }
    elif event_name == "PostToolUse":
        out = post_handler(payload)
    else:
        out = {}

    sys.stdout.write(json.dumps(out or {}, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    if exit_code:
        sys.exit(exit_code)
