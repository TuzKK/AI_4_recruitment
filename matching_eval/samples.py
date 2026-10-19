"""Private sample manifest validation and local PDF text extraction."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def load_manifest(root: Path) -> list[dict]:
    """Return samples only after checking labels, paths, IDs and every file hash."""
    root = Path(root).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not isinstance(
        manifest.get("samples"), list
    ):
        raise ValueError("unsupported sample manifest")
    samples = manifest["samples"]
    ids: set[str] = set()
    hashes: set[str] = set()
    for sample in samples:
        relative = Path(sample["file"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path.suffix.lower() != ".pdf":
            raise ValueError("sample path escapes directory")
        if sample["label"] not in ("high_match", "rejected"):
            raise ValueError("unknown sample label")
        if sample["id"] in ids or sample["sha256"] in hashes:
            raise ValueError("duplicate sample")
        if sample["id"].startswith("A") != (sample["label"] == "high_match"):
            raise ValueError("sample ID and label disagree")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sample["sha256"]:
            raise ValueError(f"sample hash changed: {sample['id']}")
        ids.add(sample["id"])
        hashes.add(digest)
    return samples


def extract_pdf_text(path: Path) -> str:
    """Extract text with Poppler or pypdf; flag empty or image-only PDFs."""
    path = Path(path)
    try:
        completed = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
    else:
        if completed.returncode:
            raise ValueError(f"PDF text extraction failed: {path.name}")
        text = completed.stdout.decode("utf-8", errors="replace").replace("\f", "\n").strip()
    if len(text) < 200:
        raise ValueError(f"PDF text coverage too short: {path.name}")
    return text
