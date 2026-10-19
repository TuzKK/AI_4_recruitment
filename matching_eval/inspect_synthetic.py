"""Inspect the local licensed synthetic corpus before hand-curating a test set."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TERMS = {
    "本体": 6, "知识图谱": 6, "数据建模": 5, "数据治理": 5,
    "数据仓库": 4, "数据清洗": 4, "数据接入": 4, "字段映射": 4,
    "SQL": 4, "Python": 4, "JavaScript": 4, "ETL": 4,
    "项目交付": 4, "软件实施": 4, "系统实施": 4, "系统配置": 4,
    "数据处理": 3, "数据分析": 2, "数据库": 2,
    "大数据": 2, "软件开发": 2, "项目管理": 1,
    "客户需求": 2, "系统测试": 1, "技术支持": 1,
}


def inspect(source: Path) -> list[dict]:
    results = []
    for path in source.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        work = record.get("workExperience", [])
        education = record.get("education", [])
        positions = [item.get("position", "").strip() for item in work]
        descriptions = [item.get("jobDescription", "").strip() for item in work]
        degrees = [item.get("degreeLevel", "").strip() for item in education]
        majors = [item.get("major", "").strip() for item in education]
        text = "\n".join(positions + descriptions + degrees + majors)
        hits = [term for term in TERMS if re.search(
            r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text, re.I)]
        results.append({"source_id": path.stem, "score": sum(TERMS[t] for t in hits),
                        "hits": hits, "positions": positions, "degrees": degrees,
                        "majors": majors, "description_chars": sum(map(len, descriptions)),
                        "text_chars": len(text)})
    return sorted(results, key=lambda r: (-r["score"], -r["description_chars"], int(r["source_id"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rows = inspect(root / "source" / "SyntheticResumeData" / "result_gt")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"inspected {len(rows)} synthetic resumes")
