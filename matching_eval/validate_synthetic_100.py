"""Verify synthetic resume exports and report likely template duplicates."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "Samples_for_optimization/synthetic_100"
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


def shingles(text: str) -> set[str]:
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z]+", "", text).lower()
    return {text[index:index + 6] for index in range(max(0, len(text) - 5))}


def main() -> None:
    samples = MANIFEST["samples"]
    assert len(samples) == 100
    assert len({row["source_id"] for row in samples}) == 100
    assert len({row["pdf_sha256"] for row in samples}) == 100
    labels = Counter(row["label"] for row in samples)
    assert labels["hard_negative"] == 20
    assert dict(labels) == MANIFEST["label_counts"]
    assert len(list((ROOT / "pdf").glob("*.pdf"))) == 100
    assert len(list((ROOT / "text").glob("*.txt"))) == 100
    texts = {}
    for row in samples:
        pdf = (ROOT / row["pdf"]).read_bytes()
        content = (ROOT / row["text"]).read_bytes()
        assert pdf.startswith(b"%PDF")
        assert hashlib.sha256(pdf).hexdigest() == row["pdf_sha256"]
        assert hashlib.sha256(content).hexdigest() == row["text_sha256"]
        assert len(content) >= 200
        texts[row["id"]] = shingles(content.decode("utf-8"))
    similarities = []
    for left, right in combinations(samples, 2):
        a, b = texts[left["id"]], texts[right["id"]]
        score = len(a & b) / len(a | b) if a or b else 0
        if score >= 0.52:
            similarities.append((round(score, 3), left["id"], right["id"],
                                 left["source_id"], right["source_id"]))
    print(f"verified 100 PDFs and 100 texts; labels={dict(labels)}")
    print(f"similar pairs >=0.52: {len(similarities)}")
    for pair in sorted(similarities, reverse=True)[:25]:
        print(*pair)


if __name__ == "__main__":
    main()
