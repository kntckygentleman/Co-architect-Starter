#!/usr/bin/env python3
"""Cross-platform host architecture, Python runtime, shell, and timezone detector.

Zero external dependencies (Python 3.9+ stdlib only). Supports macOS (Darwin arm64/x86_64),
Linux (native & WSL2), and Windows (10/11 PowerShell/cmd).
"""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any


def _detect_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    proc_ver = Path("/proc/version")
    if proc_ver.is_file():
        try:
            txt = proc_ver.read_text(encoding="utf-8", errors="ignore").lower()
            return "microsoft" in txt or "wsl" in txt
        except OSError:
            pass
    return False


def _detect_iana_timezone() -> str:
    env_tz = os.environ.get("TZ", "").strip()
    if env_tz and "/" in env_tz and not env_tz.startswith(":"):
        return env_tz

    localtime_path = Path("/etc/localtime")
    if localtime_path.is_symlink():
        for raw_target in (os.readlink(localtime_path), str(localtime_path.resolve())):
            m = re.search(
                r"zoneinfo/([A-Za-z0-9_+-]+/[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)?)$",
                raw_target,
            )
            if m:
                return m.group(1)

    etc_tz = Path("/etc/timezone")
    if etc_tz.is_file():
        try:
            val = etc_tz.read_text(encoding="utf-8", errors="ignore").strip()
            if val and "/" in val:
                return val
        except OSError:
            pass

    if os.name == "nt":
        try:
            tz_name = datetime.now().astimezone().tzname() or "UTC"
            return tz_name
        except Exception:
            return "UTC"

    try:
        tz_name = datetime.now().astimezone().tzname() or "UTC"
        return tz_name
    except Exception:
        return "UTC"


def _resolve_python_command() -> tuple[str, str]:
    """Return (executable_path, hook_invoker_token) suitable for hooks.json on this OS."""
    exe = os.path.abspath(sys.executable) if sys.executable else ""
    if os.name == "nt":
        if exe and os.path.isfile(exe):
            norm_exe = exe.replace("\\", "/")
            invoker = f'"{norm_exe}"' if " " in norm_exe else norm_exe
            return norm_exe, invoker
        py_launcher = shutil.which("py")
        if py_launcher:
            return py_launcher.replace("\\", "/"), "py -3"
        return "python", "python"

    for cand_name in ("python3", "python"):
        found = shutil.which(cand_name)
        if found:
            try:
                out = subprocess.check_output(
                    [found, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    text=True,
                ).strip()
                parts = [int(x) for x in out.split(".")[:2]]
                if len(parts) == 2 and (parts[0] > 3 or (parts[0] == 3 and parts[1] >= 9)):
                    return found, cand_name
            except Exception:
                continue

    if exe and os.path.isfile(exe):
        invoker = f'"{exe}"' if " " in exe else exe
        return exe, invoker
    return "python3", "python3"


def format_hook_command(python_invoker: str, script_path: Path, event_name: str) -> str:
    """Format a cross-platform command string for Antigravity .agents/hooks.json."""
    abs_script = str(script_path.resolve())
    if os.name == "nt":
        abs_script = abs_script.replace("\\", "/")
    quoted_script = f'"{abs_script}"' if " " in abs_script else abs_script
    return f"{python_invoker} {quoted_script} {event_name}"


def detect_host_environment(target_workspace: Path | None = None) -> dict[str, Any]:
    """Inspect host OS, CPU architecture, Python runtime, shell, timezone, and Antigravity dirs."""
    ws_root = (target_workspace or Path.cwd()).resolve()
    os_system = platform.system() or ("Windows" if os.name == "nt" else "POSIX")
    is_wsl = _detect_wsl() if os_system == "Linux" else False
    machine_arch = platform.machine() or "unknown"
    py_exe, py_invoker = _resolve_python_command()
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    if os.name == "nt":
        shell_name = "pwsh/powershell" if os.environ.get("PSModulePath") else (os.environ.get("COMSPEC") or "cmd.exe")
        file_lock_backend = "msvcrt"
    else:
        shell_name = os.path.basename(os.environ.get("SHELL") or "/bin/sh")
        file_lock_backend = "fcntl"

    home_dir = Path.home()
    agy_app_dir = home_dir / ".gemini" / "antigravity"
    agy_cfg_dir = home_dir / ".gemini" / "config"
    mcp_cfg_file = agy_cfg_dir / "mcp_config.json"

    kortex_detected = False
    if mcp_cfg_file.is_file():
        try:
            # Read-only existence sniff of server key names without reading credentials
            raw = mcp_cfg_file.read_text(encoding="utf-8", errors="ignore")
            kortex_detected = '"kortex"' in raw
        except OSError:
            kortex_detected = False

    hooks_script = ws_root / ".agents" / "scripts" / "workspace_hooks.py"
    return {
        "os_system": os_system,
        "os_release": platform.release(),
        "is_wsl": is_wsl,
        "os_family": "nt" if os.name == "nt" else "posix",
        "machine_arch": machine_arch,
        "python_version": py_version,
        "python_executable": py_exe,
        "python_hook_invoker": py_invoker,
        "shell": shell_name,
        "file_lock_backend": file_lock_backend,
        "timezone": _detect_iana_timezone(),
        "workspace_root": str(ws_root),
        "antigravity_detected": agy_app_dir.is_dir() or agy_cfg_dir.is_dir(),
        "kortex_mcp_detected": kortex_detected,
        "sample_hook_command": format_hook_command(py_invoker, hooks_script, "SessionStart"),
    }
