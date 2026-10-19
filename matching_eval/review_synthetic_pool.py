"""Extract full PDFs and produce compact evidence for sample-by-sample review."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from matching_eval.samples import extract_pdf_text


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/SyntheticResumeData"
POOL = json.loads((ROOT / ".runtime/synthetic_review_pool.json").read_text(encoding="utf-8"))
OUT = ROOT / ".runtime/synthetic_pdf_review.json"
KEYWORDS = (
    "本体", "知识图谱", "数据建模", "数据治理", "数据仓库", "数据清洗", "数据处理",
    "数据分析", "数据接入", "字段映射", "数据库", "SQL", "Python", "JavaScript",
    "项目交付", "项目实施", "软件实施", "系统实施", "技术支持", "客户需求",
    "测试", "调试", "ETL", "Agent", "工作流", "软件开发", "前端开发", "大数据",
)


def redact(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?<!\d)1[3-9]\d[ -]?\d{4}[ -]?\d{4}(?!\d)", "[PHONE]", text)
    text = re.sub(r"(?<!\d)(?:0\d{2,3}[- ]?)?\d{7,8}(?!\d)", "[PHONE]", text)
    text = re.sub(r"((?:电话|手机|电\s*话|联系方式)\s*[:：/]\s*)[+()\d\s-]{7,20}",
                  r"\1[PHONE]", text)
    return text


def evidence(text: str, term: str) -> str | None:
    match = re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text, re.I)
    if not match:
        return None
    return " ".join(text[max(0, match.start() - 55):match.end() + 85].split())


def main() -> None:
    rows = []
    for item in POOL:
        source_id = item["source_id"]
        pdf = SOURCE / "resume_list_pdf" / f"{source_id}.pdf"
        annotation = json.loads((SOURCE / "result_gt" / f"{source_id}.json").read_text(encoding="utf-8"))
        content = redact(extract_pdf_text(pdf))
        hits = {term: snippet for term in KEYWORDS if (snippet := evidence(content, term))}
        rows.append({
            "source_id": source_id,
            "pool_group": item["pool_group"],
            "positions": [x.get("position", "") for x in annotation.get("workExperience", [])],
            "education": [{k: x.get(k, "") for k in ("degreeLevel", "major")}
                          for x in annotation.get("education", [])],
            "chars": len(content),
            "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "text_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "hits": hits,
            "full_text": content,
        })
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"reviewed PDF extraction for {len(rows)} samples; empty={sum(r['chars'] < 100 for r in rows)}")


if __name__ == "__main__":
    main()
