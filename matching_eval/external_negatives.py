"""Reproduce the separately licensed, unrelated Chinese resume test subset."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

SOURCE_COMMIT = "3ecd09129f65955e743aacf67f2785fcee10d461"
SOURCE_URL = "https://github.com/jijunhao/SyntheticResumeData"
SOURCE_IDS = [
    ("1246", "临床护理"), ("994", "教育教学"), ("1098", "渠道销售"),
    ("2938", "平面设计"), ("2752", "市场推广"), ("386", "民事法律"),
    ("1019", "人事行政"), ("1070", "财务会计"), ("2178", "临床医疗"),
    ("2908", "摄影新闻"),
]


def export(source: Path, destination: Path) -> dict:
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    commit = subprocess.check_output(["git", "-c", f"safe.directory={source}",
                                      "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if commit != SOURCE_COMMIT or not (source / "LICENSE").is_file():
        raise ValueError("source commit or license differs from audited corpus")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "LICENSE").write_bytes((source / "LICENSE").read_bytes())
    entries = []
    for number, (source_id, role) in enumerate(SOURCE_IDS, 1):
        record = json.loads((source / "result_gt" / f"{source_id}.json").read_text(encoding="utf-8"))
        parts = []
        seen = set()
        for work in record.get("workExperience", []):
            position = work.get("position", "").strip()
            description = work.get("jobDescription", "").strip()
            item = "\n".join(value for value in (position, description) if value)
            if item and item not in seen:
                parts.append(item)
                seen.add(item)
        for education in record.get("education", []):
            item = " / ".join(value for value in (education.get("degreeLevel", ""),
                                                   education.get("major", "")) if value).strip()
            if item and item not in seen:
                parts.append(item)
                seen.add(item)
        content = "\n\n".join(parts).strip() + "\n"
        content = re.sub(r"\b1[3-9]\d{9}\b", "[PHONE]", content)
        content = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", content)
        if len(content) < 100:
            raise ValueError(f"external resume text too short: {source_id}")
        name = f"N{number:03}.txt"
        path = destination / name
        path.write_text(content, encoding="utf-8")
        entries.append({"id": path.stem, "label": "rejected", "role": role,
                        "source_annotation": f"result_gt/{source_id}.json", "file": name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"schema_version": 1, "source_url": SOURCE_URL, "source_commit": SOURCE_COMMIT,
                "license": "Apache-2.0", "selection": "人工挑选与本体实施交付无关的职业；仅供负例压力测试",
                "samples": entries}
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
    return manifest


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = export(root / "source" / "SyntheticResumeData",
                    root / "Samples_for_optimization" / "external_negative")
    print(f"exported {len(result['samples'])} synthetic negative examples")
