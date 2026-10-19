"""Select a diverse PDF review pool from the synthetic resume annotations."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads((ROOT / ".runtime/synthetic_curation.json").read_text(encoding="utf-8"))
EXCLUDED = {1246, 994, 1098, 2938, 2752, 386, 1019, 1070, 2178, 2908}


def signature(row: dict) -> str:
    parts = row["positions"] + row["majors"]
    return re.sub(r"[\s\W]+", "", "|".join(parts).lower())


selected: list[dict] = []
seen: set[str] = set()


def take(row: dict, group: str) -> bool:
    if int(row["source_id"]) in EXCLUDED:
        return False
    key = signature(row)
    if not key or key in seen:
        return False
    seen.add(key)
    selected.append({"source_id": row["source_id"], "pool_group": group})
    return True


for row in ROWS:
    if len(selected) >= 100:
        break
    if row["score"] >= 3:
        take(row, "adjacent")

easy_terms = ("护士", "医生", "教师", "厨师", "会计", "律师", "销售", "设计师", "记者", "行政", "翻译", "导游", "人力资源")
for row in ROWS:
    if len(selected) >= 135:
        break
    if row["score"] <= 2 and any(t in "|".join(row["positions"]) for t in easy_terms):
        take(row, "distant")

output = ROOT / ".runtime/synthetic_review_pool.json"
output.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"selected {len(selected)} PDFs for content review")
