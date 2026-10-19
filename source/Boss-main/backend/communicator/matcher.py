"""LLM-based pre-screening matcher.

Formats raw JD JSON and candidate card data into readable text,
then evaluates match quality using the 5-dimension scoring rubric.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from communicator.prompts import PRE_MATCH_SYSTEM, PRE_MATCH_USER
from utils.llm_client import llm

logger = logging.getLogger(__name__)


def pre_match_candidate(
    jd_summary: str,
    candidate_profile: str,
) -> dict[str, Any]:
    """Score a candidate against the position using LLM.

    Args:
        jd_summary: JSON string of JD data from position analysis.
        candidate_profile: JSON string of candidate card data.

    Returns:
        dict with score, dimension scores, reasons, recommendation.
    """
    # ── Format JD as readable text ──
    jd_text = _format_jd(jd_summary)

    # ── Format candidate as readable text ──
    candidate_text = _format_candidate(candidate_profile)

    user_prompt = PRE_MATCH_USER.format(
        jd_text=jd_text,
        candidate_text=candidate_text,
    )

    result = llm.chat_json(
        system_prompt=PRE_MATCH_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.2,
        max_tokens=2048,
    )

    score = result.get("score", 0)
    if isinstance(score, str):
        try:
            score = int(score)
        except ValueError:
            score = 0
    result["score"] = score

    logger.info(
        "Pre-match: %d 分 — %s | reasons: %s | concerns: %s",
        score,
        result.get("recommendation", "?"),
        result.get("match_reasons", []),
        result.get("concern_reasons", []),
    )
    return result


def _format_jd(jd_json_str: str) -> str:
    """Convert raw JD JSON into human-readable text for the LLM."""
    try:
        jd = json.loads(jd_json_str)
    except (json.JSONDecodeError, TypeError):
        return jd_json_str  # Already text

    lines = []

    # Title & summary
    lines.append(f"职位：{jd.get('title', '未知')}")
    summary = jd.get('summary', '')
    if summary:
        lines.append(f"简介：{summary}")

    # Responsibilities
    duties = jd.get('responsibilities', [])
    if duties:
        lines.append("职责：")
        for d in duties:
            lines.append(f"  - {d}")

    # Requirements (hard)
    reqs = jd.get('requirements', [])
    if reqs:
        lines.append("硬性要求：")
        for r in reqs:
            lines.append(f"  - {r}")

    # Preferred
    pref = jd.get('preferred', [])
    if pref:
        lines.append("加分项：")
        for p in pref:
            lines.append(f"  - {p}")

    # Skills
    skills = jd.get('skills', [])
    if skills:
        lines.append(f"核心技能：{', '.join(skills)}")

    # Search keywords (from position analysis)
    primary_kw = jd.get('primary_keywords', [])
    if primary_kw:
        lines.append(f"搜索主关键词：{', '.join(primary_kw[:10])}")

    must_have = jd.get('must_have_skills', [])
    if must_have:
        lines.append(f"必备技能：{', '.join(must_have)}")

    # Scorecard criteria
    sc = jd.get('scorecard', {})
    if isinstance(sc, dict) and sc:
        lines.append("评分标准参考：")
        if sc.get('skill_match_criteria'):
            lines.append(f"  技能：{sc['skill_match_criteria'][:200]}")
        if sc.get('experience_criteria'):
            lines.append(f"  经验：{sc['experience_criteria'][:200]}")
        if sc.get('education_criteria'):
            lines.append(f"  学历：{sc['education_criteria'][:200]}")

    return "\n".join(lines)


def _format_candidate(profile_json_str: str) -> str:
    """Convert candidate card JSON into a detailed, structured text for LLM scoring."""
    try:
        card = json.loads(profile_json_str)
    except (json.JSONDecodeError, TypeError):
        return profile_json_str

    lines = []

    # ── Header ──
    name = card.get('name', '未知')
    salary = card.get('salary', '')
    lines.append(f"候选人：{name}" + (f" | 期望薪资 {salary}" if salary else ""))

    # ── Base info ──
    base_info = card.get('base_info', '')
    if base_info:
        lines.append(f"基本条件：{base_info}")

    active = card.get('active', '')
    if active:
        lines.append(f"活跃状态：{active}")

    # ── Expect ──
    expect_parts = []
    if card.get('expect_city'):
        expect_parts.append(f"期望城市：{card['expect_city']}")
    if card.get('expect_position'):
        expect_parts.append(f"期望职位：{card['expect_position']}")
    if expect_parts:
        lines.append(" | ".join(expect_parts))

    # ── Self-description (THIS is the key data for matching!) ──
    advantages = card.get('advantages', '')
    if advantages:
        lines.append(f"个人自述：{advantages[:500]}")

    # ── Skill tags ──
    tags = card.get('tags', [])
    clean_tags = [t for t in tags if len(t) >= 2 and not _is_noise(t)]
    if clean_tags:
        lines.append(f"技能：{', '.join(clean_tags)}")

    # ── Work experience ──
    work = card.get('work_experience', [])
    if work:
        lines.append("工作经历：")
        for w in work[:5]:
            lines.append(f"  • {w}")

    # ── Education ──
    edu = card.get('education', [])
    if edu:
        lines.append(f"教育背景：{' | '.join(edu)}")

    return "\n".join(lines)


def _is_noise(text: str) -> bool:
    """Filter out noise from tags: dates, pure numbers, city names, symbols."""
    if text in ("合肥", "北京", "上海", "深圳", "广州", "杭州", "成都", "武汉",
                "南京", "苏州", "天津", "重庆", "西安", "长沙", "郑州", "东莞",
                "佛山", "宁波", "青岛", "厦门", "福州", "无锡", "合肥", "济南"):
        return True
    if "本周" in text and "BOSS" in text:
        return True
    if "分钟前" in text or "小时前" in text:
        return True
    if "为你推荐" in text or "相似" in text:
        return True
    if text in ("正在搜索", "筛选", "期望", "优势", "经历", "在线简历", "新牛人"):
        return True
    return _is_not_tag(text)


def _is_not_tag(text: str) -> bool:
    """Filter out items that are clearly NOT skill/domain tags."""
    # Dates
    if len(text) <= 6 and all(c.isdigit() or c in '.-' for c in text):
        return True
    # Numbers-only or measurement
    if text.replace('.', '').replace('%', '').isdigit():
        return True
    # Pure symbols/emoji
    if not any(c.isalpha() for c in text) and not any('一' <= c <= '鿿' for c in text):
        return True
    return False
