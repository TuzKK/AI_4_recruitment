"""Export a reviewed, reproducible set of 100 synthetic resume PDFs."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/SyntheticResumeData"
DEST = ROOT / "Samples_for_optimization/synthetic_100"
POOL = json.loads((ROOT / ".runtime/synthetic_pdf_review.json").read_text(encoding="utf-8"))
BY_ID = {row["source_id"]: row for row in POOL}
COMMIT = "3ecd09129f65955e743aacf67f2785fcee10d461"

# Adjudicated from the complete PDF text. A missing item means no evidence in the
# resume, not proof that the person lacks the skill.
HARD_GAPS = {
    "26": "Python/SQL 数据分析经历接近岗位，但本科为市场营销，且缺少系统实施与本体配置证据。",
    "440": "有数据清洗、Python 和平台经历，但简历没有 SQL 查询/核对能力或实施交付证据。",
    "2541": "有数据工程和清洗建模经历，但没有明确 SQL 与 Python/JavaScript 编码证据。",
    "770": "有数据清洗和自动化测试实习，但没有明确 SQL 与 Python/JavaScript 技能证据。",
    "1496": "计算机专业且做过大数据处理，但履历偏短期实习，没有 SQL、Python/JavaScript 或交付证据。",
    "771": "信息管理专业和数据清洗实习相近，但没有 SQL 与 Python/JavaScript 编码证据。",
    "1522": "具备 T-SQL 数据库维护，主体却是电气自动化硬件项目，未见 Python/JavaScript 与数据平台交付。",
    "2319": "写有数据建模和平台实施，但商学背景且没有 SQL 与 Python/JavaScript 的明确证据。",
    "470": "数据科学、清洗和项目实施经历接近，但简历未明确 SQL 或 Python/JavaScript，且偏分析岗位。",
    "1838": "有数据建模与 Python，未见 SQL 查询清洗/核对和客户实施证据。",
    "2937": "商业数据指标和数据库改进相近，但主要是市场分析，未见 SQL、Python/JavaScript 或技术交付。",
    "1195": "软件实施和验收字样相近，正文大量为材料制造质检，未见 SQL 与 Python/JavaScript。",
    "283": "计算机学历与 Python 开发相近，但以产品助理和短期实习为主，未见 SQL 与数据实施。",
    "2744": "计算机学历且会 Python/JavaScript，经历集中于前端页面开发，未见 SQL 和数据建模/接入。",
    "942": "软件工程与 Python 测试相近，但主要做支付模块和自动化测试，未见 SQL 与数据实施。",
    "2306": "具备 JavaScript 和客户需求工作，但以 UI/GUI 设计为主，未见 SQL、数据处理和实施交付。",
    "2652": "有前端 JavaScript 开发，未见 SQL、数据建模或客户实施交付。",
    "651": "有前端 JavaScript 开发与调试，未见 SQL、数据处理或实施交付。",
    "387": "有前端 JavaScript 开发，未见 SQL、数据处理或客户交付。",
    "831": "会 Python/JavaScript 并做软件开发，但简历聚焦前端/应用开发，未见 SQL 数据核对与建模交付。",
}

EASY_IDS = (
    "42", "2063", "2768", "722", "2831", "2919", "1973", "693", "674", "1276",
    "944", "1275", "352", "1166", "481", "371", "2895", "2930", "2857", "2355",
)
STRONG_IDS = {"611", "609", "1054", "992", "2907", "2404", "17"}
QUALITY_FLAGS = {
    "2435": ["正文混入与软件/数据经历不相符的护理技能叙述"],
    "2541": ["出生日期与教育/工作时间线矛盾"],
    "1195": ["软件开发经历混入大量材料制造质检任务"],
    "1838": ["自我介绍所写毕业院校与教育经历不一致"],
}
OTHER_NEGATIVE_IDS = {
    "2405", "1197", "338", "951", "2710", "2969", "255", "415", "2403", "1847",
    "2864", "2341", "2361",
}


def category_for(row: dict) -> tuple[str, str]:
    source_id = row["source_id"]
    if source_id in HARD_GAPS:
        return "hard_negative", HARD_GAPS[source_id]
    if source_id in EASY_IDS:
        return "ordinary_negative", "主要经历为" + "、".join(row["positions"][:2]) + "，未见岗位核心数据实施与编程证据。"
    if source_id in STRONG_IDS:
        return "strong_match", "简历明确呈现相关学历、SQL、Python/JavaScript 与数据处理/实施的组合证据。"
    if source_id in OTHER_NEGATIVE_IDS:
        return "ordinary_negative", "存在少量相邻术语，但主要工作方向与数据建模实施交付不符。"
    return "borderline", "具备部分数据、开发或交付经历；SQL、编程、实施三方面的组合证据尚不充分。"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def review_evidence(row: dict) -> list[str]:
    ordered = ("本体", "知识图谱", "数据建模", "数据清洗", "项目实施", "软件实施",
               "SQL", "Python", "JavaScript", "数据处理", "数据分析", "客户需求")
    snippets = [row["hits"][term][:125] for term in ordered if term in row["hits"]]
    if snippets:
        return snippets[:3]
    return ["职位/经历：" + "、".join(row["positions"][:2])]


def main() -> None:
    hard = [BY_ID[source_id] for source_id in HARD_GAPS]
    easy = [BY_ID[source_id] for source_id in EASY_IDS]
    adjacent = [row for row in POOL if row["pool_group"] == "adjacent"
                and row["source_id"] not in HARD_GAPS and row["source_id"] not in EASY_IDS][:59]
    adjacent.append(BY_ID["17"])
    selected = adjacent + hard + easy
    assert len(selected) == len({row["source_id"] for row in selected}) == 100
    labels = Counter(category_for(row)[0] for row in selected)
    assert labels["hard_negative"] == 20
    (DEST / "pdf").mkdir(parents=True, exist_ok=True)
    (DEST / "text").mkdir(parents=True, exist_ok=True)
    samples = []
    for number, row in enumerate(selected, 1):
        sample_id = f"S{number:03d}"
        source_id = row["source_id"]
        source_pdf = SOURCE / "resume_list_pdf" / f"{source_id}.pdf"
        pdf_data = source_pdf.read_bytes()
        text_data = (row["full_text"].strip() + "\n").encode("utf-8")
        label, reason = category_for(row)
        pdf_rel = f"pdf/{sample_id}.pdf"
        text_rel = f"text/{sample_id}.txt"
        (DEST / pdf_rel).write_bytes(pdf_data)
        (DEST / text_rel).write_bytes(text_data)
        stage_expectation = {
            "strong_match": ("pass", "pass"),
            "borderline": ("pass", "review"),
            "hard_negative": ("pass", "reject"),
            "ordinary_negative": ("reject", "reject"),
        }
        coarse, fine = stage_expectation[label]
        samples.append({
            "id": sample_id, "label": label, "source_id": source_id,
            "expected_coarse": coarse, "expected_fine": fine,
            "source_pdf": f"resume_list_pdf/{source_id}.pdf",
            "source_annotation": f"result_gt/{source_id}.json",
            "pdf": pdf_rel, "text": text_rel,
            "pdf_sha256": sha256(pdf_data), "text_sha256": sha256(text_data),
            "positions": row["positions"], "education": row["education"],
            "evidence_terms": list(row["hits"]),
            "review_evidence": review_evidence(row),
            "review_note": reason,
            "quality_flags": QUALITY_FLAGS.get(source_id, []),
        })
    manifest = {
        "schema_version": 1,
        "purpose": "本体建模实施与交付工程师（伙伴）粗筛/精筛样本调优",
        "source_url": "https://github.com/jijunhao/SyntheticResumeData",
        "source_commit": COMMIT,
        "license": "Apache-2.0",
        "data_type": "合成简历；不是真实候选人或人工招聘结果",
        "review_basis": "PDF 全文提取后按本次岗位要求逐份复核；缺少证据不等于证明候选人缺少能力",
        "label_counts": dict(labels),
        "samples": samples,
    }
    (DEST / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(ROOT / ".runtime/synthetic_LICENSE", DEST / "LICENSE")
    print(f"exported {len(samples)} samples: {dict(labels)}")


if __name__ == "__main__":
    main()
