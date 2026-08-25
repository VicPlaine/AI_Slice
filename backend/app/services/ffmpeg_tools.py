"""Resolve FFmpeg/FFprobe binaries from PATH or common local project folders."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.config import settings


def _candidate_bin_dirs() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[3]
    backend_root = repo_root / "backend"

    configured_dir = settings.ffmpeg_bin_dir.strip()
    candidates = [
        Path(configured_dir) if configured_dir else None,
        repo_root / "tools" / "ffmpeg" / "bin",
        repo_root / "ffmpeg" / "bin",
        backend_root / "tools" / "ffmpeg" / "bin",
    ]

    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue

        resolved = candidate.expanduser().resolve()
        key = str(resolved).lower()
        if key in seen:
            continue

        seen.add(key)
        result.append(resolved)

    return result


def find_command(command: str) -> str | None:
    """Resolve a command from PATH or supported project-local FFmpeg directories."""
    resolved = shutil.which(command)
    if resolved:
        return resolved

    for bin_dir in _candidate_bin_dirs():
        for executable_name in (command, f"{command}.exe"):
            executable = bin_dir / executable_name
            if executable.exists():
                return str(executable)

    return None


def require_command(command: str, purpose: str) -> str:
    """Resolve a command or raise a clear error with local-folder hints."""
    resolved = find_command(command)
    if resolved:
        return resolved

    raise FileNotFoundError(
        f"Missing required command: {command}. "
        f"This step needs it to {purpose}. "
        "Install FFmpeg and add ffmpeg.exe / ffprobe.exe to PATH, "
        "or place them in tools/ffmpeg/bin under the project root."
    )
