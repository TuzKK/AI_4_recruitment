"""CHANGELOG parsing helpers shared by GUI dialogs and updater."""
from __future__ import annotations

import sys
from pathlib import Path


def normalize_version(version: str) -> str:
    """Return a comparable version string without a leading ``v``."""
    return str(version).strip().lstrip("vV")


def split_version_heading(line: str) -> tuple[str, str]:
    """Parse a ``## vX.Y`` changelog heading into ``(tag, subtitle)``."""
    rest = line[3:].strip()
    tag = rest.split("—")[0].split("–")[0].split()[0].strip()
    if "—" in rest:
        subtitle = rest.split("—", 1)[1].strip()
    elif "–" in rest:
        subtitle = rest.split("–", 1)[1].strip()
    else:
        subtitle = ""
    return tag, subtitle


def parse_changelog_versions(content: str) -> list[tuple[str, str, str]]:
    """Parse CHANGELOG content into ``(tag, heading_line, section_text)`` rows."""
    versions: list[tuple[str, str, str]] = []
    current_version: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## v"):
            if current_version:
                versions.append((current_version, current_lines[0], "\n".join(current_lines)))
            current_version, _ = split_version_heading(line)
            current_lines = [line]
        elif current_version:
            current_lines.append(line)

    if current_version:
        versions.append((current_version, current_lines[0], "\n".join(current_lines).rstrip()))

    return versions


def extract_changelog_section(content: str, target_version: str, include_heading: bool = False) -> str | None:
    """Extract one version section from CHANGELOG content."""
    target = normalize_version(target_version)
    for tag, heading, section in parse_changelog_versions(content):
        if normalize_version(tag) == target:
            if include_heading:
                return section
            lines = section.splitlines()
            return "\n".join(lines[1:]) if len(lines) > 1 else ""
    return None


def resolve_local_changelog_path(base_dir: Path) -> Path | None:
    """Return the packaged or source CHANGELOG path, if present."""
    meipass = getattr(sys, "_MEIPASS", None)
    packaged = (Path(meipass) / "CHANGELOG.md") if meipass else None
    if packaged and packaged.exists():
        return packaged

    source = Path(base_dir) / "CHANGELOG.md"
    return source if source.exists() else None
