"""Evidence-checked scoring for the ontology implementation role."""

from __future__ import annotations

import re
from typing import Any

WEIGHTS = {
    "data_implementation": 25,
    "delivery": 25,
    "sql": 15,
    "coding_logic": 15,
    "modeling": 10,
    "preferred": 10,
}
STAGES = {"precontact", "full_resume"}
COVERAGES = {"complete", "partial", "unknown"}
RELEVANT_EVIDENCE = {
    "data_implementation": re.compile(
        r"数据|接入|映射|清洗|导入|初始化|ETL|对接|集成|迁移|采集|调度|pipeline",
        re.IGNORECASE,
    ),
    "delivery": re.compile(
        r"实施|交付|客户|测试|排障|上线|验收|部署|支持|核对|联调|调试|现场|项目",
        re.IGNORECASE,
    ),
    "sql": re.compile(r"SQL|数据库查询|查询语句", re.IGNORECASE),
    "coding_logic": re.compile(
        r"Python|JavaScript|TypeScript|Node\.?js|\bJS\b|Logic", re.IGNORECASE
    ),
    "modeling": re.compile(
        r"本体|知识图谱|数据模型|建模|对象|属性|关系|指标|业务规则|数据仓库|数仓",
        re.IGNORECASE,
    ),
    "preferred": re.compile(
        r"Foundry|Ontology|AIP|DataAgent|Agent|Workflow|工作流|AI\s*Coding|"
        r"电力|汽车|保险|制造|供应链|Palantir|智能平台",
        re.IGNORECASE,
    ),
}
RELATED_MAJOR = re.compile(
    r"计算机|软件|数据|信息|统计|数学|人工智能|自动化|电子|通信|网络|系统工程"
)


def _supported(text: str, quote: str) -> bool:
    """Allow layout whitespace differences while requiring a verbatim source span."""
    normalized_text = re.sub(r"\s+", " ", text).casefold()
    normalized_quote = re.sub(r"\s+", " ", quote.strip()).casefold()
    return bool(normalized_quote) and normalized_quote in normalized_text


def score_candidate(
    stage: str,
    text: str,
    coverage: str,
    judgement: dict[str, Any],
    *,
    contact_threshold: int = 30,
    high_match_threshold: int = 75,
) -> dict[str, Any]:
    """Score cited job evidence; never turn a missing claim into a hard failure."""
    if stage not in STAGES or coverage not in COVERAGES:
        raise ValueError("unknown stage or coverage")
    if not isinstance(judgement, dict):
        raise TypeError("judgement must be an object")

    issues: list[str] = []
    unknowns: list[str] = []
    breakdown: dict[str, int] = {}
    levels: dict[str, int] = {}
    claims = judgement.get("criteria")
    if not isinstance(claims, dict):
        claims = {}
        issues.append("missing criteria")

    for name, weight in WEIGHTS.items():
        claim = claims.get(name)
        if (
            not isinstance(claim, dict)
            or type(claim.get("level")) is not int
            or claim["level"] not in (0, 1, 2)
        ):
            issues.append(f"invalid criterion: {name}")
            levels[name] = 0
            breakdown[name] = 0
            continue
        level = claim["level"]
        quote = claim.get("evidence")
        if level and (not isinstance(quote, str) or not _supported(text, quote)):
            issues.append(f"unsupported evidence: {name}")
            level = 0
        if (
            level
            and (stage == "full_resume" or name != "preferred")
            and not RELEVANT_EVIDENCE[name].search(quote)
        ):
            issues.append(f"irrelevant evidence: {name}")
            level = 0
        levels[name] = level
        breakdown[name] = weight * level // 2
        if level == 0:
            unknowns.append(name)

    hard_failure = False
    hard_status: dict[str, str] = {}
    for name in ("education", "travel"):
        claim = judgement.get(name)
        if not isinstance(claim, dict) or claim.get("status") not in (
            "pass",
            "fail",
            "unknown",
        ):
            issues.append(f"invalid condition: {name}")
            hard_status[name] = "unknown"
            unknowns.append(name)
            continue
        status = claim["status"]
        quote = claim.get("evidence", "")
        if status != "unknown" and (
            not isinstance(quote, str) or not _supported(text, quote)
        ):
            issues.append(f"unsupported evidence: {name}")
            status = "unknown"
        if (
            status == "pass"
            and name == "education"
            and (
                not re.search(r"本科|学士|硕士|博士", quote)
                or (stage == "full_resume" and not RELATED_MAJOR.search(quote))
            )
        ):
            issues.append("unverified education pass")
            status = "unknown"
        if status == "fail" and name == "education":
            if not re.search(r"大专|专科|高中|中专|中职|职高|初中", quote):
                issues.append("unverified hard failure: education")
                status = "unknown"
            elif re.search(r"本科|硕士|博士", text):
                issues.append("conflicting education evidence")
                status = "unknown"
        if status == "fail" and name == "travel":
            explicit_refusal = re.search(
                r"(?:不接受|不能|无法|拒绝|不考虑).{0,8}(?:出差|驻场|现场)"
                r"|(?:出差|驻场|现场).{0,8}(?:不接受|不能|无法|拒绝)",
                quote,
            )
            if not explicit_refusal:
                issues.append("unverified hard failure: travel")
                status = "unknown"
        if status == "unknown":
            unknowns.append(name)
        if status == "fail":
            hard_failure = True
        hard_status[name] = status

    score = sum(breakdown.values())
    if stage == "precontact":
        primary = max(levels["data_implementation"], levels["delivery"])
        technical = max(levels["sql"], levels["coding_logic"], levels["modeling"])
        eligible = primary == 2 and technical >= 1
    else:
        eligible = (
            coverage == "complete"
            and hard_status["education"] == "pass"
            and all(
                levels[name] >= 1
                for name in ("data_implementation", "delivery", "sql", "coding_logic")
            )
        )
    eligible = bool(
        eligible
        and coverage != "unknown"
        and not hard_failure
        and not issues
        and text.strip()
    )
    if hard_failure:
        decision = "reject" if stage == "precontact" else "not_fit"
    elif issues or coverage == "unknown" or not text.strip():
        decision = "review"
    elif stage == "precontact":
        decision = "contact" if eligible and score >= contact_threshold else "hold"
    elif coverage != "complete" or hard_status["education"] == "unknown":
        decision = "review"
    elif score >= high_match_threshold and eligible:
        decision = "high_match"
    else:
        decision = "potential" if score >= 50 else "not_fit"

    return {
        "stage": stage,
        "coverage": coverage,
        "score": score,
        "decision": decision,
        "eligible": eligible,
        "breakdown": breakdown,
        "levels": levels,
        "conditions": hard_status,
        "unknowns": unknowns,
        "issues": issues,
    }
