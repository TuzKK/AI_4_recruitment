"""Job-specific rubric validation and evidence-bound decisions."""

from __future__ import annotations

import re


def _contains(text: str, quote: str) -> bool:
    def normalize(value: str) -> str:
        # PDF wrapping can split a Chinese word across lines; retain Latin word boundaries.
        value = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", value)
        value = re.sub(r"\s*([、，；。：（）])\s*", r"\1", value)
        return re.sub(r"\s+", " ", value.strip()).casefold()
    return bool(quote.strip()) and normalize(quote) in normalize(text)


def safe_title(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", title).strip(" ._")
    title = re.sub(r"_+", "_", title)[:60].strip(" ._")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if not title or title.split(".")[0].upper() in reserved:
        raise ValueError("岗位名称不可用于目录")
    return title


def validate_rubric(job: str, rubric: dict) -> dict:
    if not isinstance(job, str) or len(job.strip()) < 20 or not isinstance(rubric, dict):
        raise ValueError("请提供完整招聘需求和评分标准")
    title = safe_title(rubric.get("title", ""))
    criteria = rubric.get("criteria")
    requirements = rubric.get("requirements")
    if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10 or not isinstance(requirements, list):
        raise ValueError("评分项或硬条件格式无效")
    keys = set()
    weight_sum = 0
    categories = set()
    for item in criteria:
        if not isinstance(item, dict) or set(item) != {"key", "name", "category", "weight", "jd_quote"}:
            raise ValueError("评分项字段无效")
        key = item["key"]
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", key) or key in keys:
            raise ValueError("评分项标识无效或重复")
        if item["category"] not in {"core", "skill", "bonus"} or not isinstance(item["name"], str):
            raise ValueError("评分项类别无效")
        if type(item["weight"]) is not int or not 1 <= item["weight"] <= 80:
            raise ValueError("评分权重无效")
        if not isinstance(item["jd_quote"], str) or not _contains(job, item["jd_quote"]):
            raise ValueError("评分项必须引用岗位原文")
        keys.add(key)
        categories.add(item["category"])
        weight_sum += item["weight"]
    if weight_sum != 100 or not {"core", "skill"} <= categories:
        raise ValueError("权重必须合计 100，且包含核心职责与技能")
    for item in requirements:
        if not isinstance(item, dict) or set(item) != {"key", "name", "stage", "jd_quote"}:
            raise ValueError("硬条件字段无效")
        key = item["key"]
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", key) or key in keys:
            raise ValueError("硬条件标识无效或重复")
        if item["stage"] not in {"resume", "conversation"} or not isinstance(item["name"], str):
            raise ValueError("硬条件阶段无效")
        if not isinstance(item["jd_quote"], str) or not _contains(job, item["jd_quote"]):
            raise ValueError("硬条件必须引用岗位原文")
        keys.add(key)
    return {"title": title, "criteria": criteria, "requirements": requirements}


def score_evidence(rubric: dict, text: str, judgement: dict, stage: str, coverage: str, threshold: int) -> dict:
    if stage not in {"precontact", "full_resume"} or coverage not in {"complete", "partial", "unknown"}:
        raise ValueError("筛选阶段或资料覆盖状态无效")
    if type(threshold) is not int or not 0 <= threshold <= 100:
        raise ValueError("阈值必须为 0 到 100 的整数")
    claims = judgement.get("claims", {}) if isinstance(judgement, dict) else {}
    requirements = judgement.get("requirements", {}) if isinstance(judgement, dict) else {}
    if not isinstance(claims, dict) or not isinstance(requirements, dict):
        claims, requirements = {}, {}
    score = 0
    levels = {}
    evidence = {}
    issues = []
    for item in rubric["criteria"]:
        key = item["key"]
        claim = claims.get(key, {})
        level = claim.get("level") if isinstance(claim, dict) else None
        quote = claim.get("evidence") if isinstance(claim, dict) else None
        if type(level) is not int or level not in (0, 1, 2) or not isinstance(quote, str):
            issues.append(f"{key}: 证据格式无效")
            level, quote = 0, ""
        elif level and not _contains(text, quote):
            issues.append(f"{key}: 证据不在候选人原文")
            level, quote = 0, ""
        levels[key] = level
        if level:
            evidence[key] = quote
        score += item["weight"] * level // 2
    hard_unknown = False
    hard_failed = False
    for item in rubric["requirements"]:
        claim = requirements.get(item["key"], {})
        status = claim.get("status") if isinstance(claim, dict) else None
        quote = claim.get("evidence") if isinstance(claim, dict) else None
        if status not in {"met", "failed", "unknown"} or not isinstance(quote, str):
            issues.append(f"{item['key']}: 条件格式无效")
            status = "unknown"
        elif status != "unknown" and not _contains(text, quote):
            issues.append(f"{item['key']}: 条件证据不在原文")
            status = "unknown"
        if item["stage"] == "resume":
            hard_unknown |= status == "unknown"
            hard_failed |= status == "failed"
    core = any(levels[i["key"]] > 0 for i in rubric["criteria"] if i["category"] == "core")
    skill = any(levels[i["key"]] > 0 for i in rubric["criteria"] if i["category"] == "skill")
    if hard_failed:
        decision = "reject" if stage == "precontact" else "not_fit"
    elif issues or coverage == "unknown":
        decision = "review"
    elif stage == "precontact":
        decision = "contact" if core and skill and score >= threshold else "hold"
    elif coverage != "complete" or hard_unknown:
        decision = "review"
    elif core and skill and score >= threshold:
        decision = "high_match"
    else:
        decision = "potential" if score >= 50 else "not_fit"
    return {"score": score, "decision": decision, "coverage": coverage, "levels": levels,
            "evidence": evidence, "issues": issues}
