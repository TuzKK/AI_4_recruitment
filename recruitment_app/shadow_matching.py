"""Hosted LLM evidence and vendored skill rules for shadow-only decisions."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ._vendor.recruiter_pro.skill_matcher import SkillMatcher
from .core import score_evidence

VOCABULARY = Path(__file__).parent / "_vendor" / "recruiter_pro" / "skills.json"
LOCAL_ALIASES = {
    "Ontology": ["本体", "本体建模", "Ontology"],
    "Knowledge Graph": ["知识图谱", "knowledge graph"],
    "Data Governance": ["数据治理", "data governance"],
    "Data Warehouse": ["数据仓库", "数仓", "data warehouse"],
    "JavaScript": ["JavaScript", "JS"],
}


@lru_cache(maxsize=1)
def _vocabulary() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    raw = json.loads(VOCABULARY.read_text(encoding="utf-8"))
    families = raw.get("families", raw)
    aliases: dict[str, tuple[str, ...]] = {}
    index: dict[str, str] = {}
    for entries in families.values():
        if not isinstance(entries, dict):
            continue
        for canonical, names in entries.items():
            if not isinstance(names, list):
                continue
            aliases[canonical] = tuple({canonical, *map(str, names)})
    for canonical, names in LOCAL_ALIASES.items():
        aliases[canonical] = tuple(names)
    for canonical, names in aliases.items():
        for name in names:
            index[name.casefold()] = canonical
    return index, aliases


def _mentions(text: str, alias: str) -> bool:
    if len(alias.strip()) < 2:
        return False
    left = r"(?<![A-Za-z0-9])" if alias[0].isascii() and alias[0].isalnum() else ""
    right = r"(?![A-Za-z0-9])" if alias[-1].isascii() and alias[-1].isalnum() else ""
    return re.search(left + re.escape(alias) + right, text, re.IGNORECASE) is not None


class ShadowMatcher:
    def __init__(self):
        index, self.aliases = _vocabulary()
        self.skills = SkillMatcher(index)
        self._job_skill_cache: dict[str, list[str]] = {}

    def _extract(self, text: str, allowed: set[str] | None = None) -> list[str]:
        result = []
        for canonical, names in self.aliases.items():
            if allowed is not None and canonical not in allowed:
                continue
            if any(_mentions(text, alias) for alias in names):
                result.append(canonical)
        return result

    def skill_matches(self, requirement: str, resume: str, preferred: str = "") -> dict:
        for text in (requirement, preferred):
            if text not in self._job_skill_cache:
                if len(self._job_skill_cache) >= 128:
                    self._job_skill_cache.clear()
                self._job_skill_cache[text] = self._extract(text)
        required = self._job_skill_cache[requirement]
        bonus = [s for s in self._job_skill_cache[preferred] if s not in required]
        candidate = self._extract(resume, set(required + bonus))
        match = self.skills.match(candidate, required, bonus)
        ratio = match.match_ratio
        if required and not bonus:
            ratio = min(1.0, ratio / 0.85)
        return {"matched": match.matched_skills, "missing": match.missing_skills,
                "required": required, "preferred": bonus,
                "ratio": ratio if required or bonus else None}

    def score(self, rubric: dict, text: str, judgement: dict, stage: str,
              coverage: str, threshold: int) -> dict:
        original = score_evidence(rubric, text, judgement, stage, coverage, threshold)
        zero_gate = score_evidence(rubric, text, judgement, stage, coverage, 0)
        required_text = " ".join(i["name"] + " " + i["jd_quote"] for i in rubric["criteria"]
                                 if i["category"] == "skill")
        preferred_text = " ".join(i["name"] + " " + i["jd_quote"] for i in rubric["criteria"]
                                  if i["category"] == "bonus")
        skills = self.skill_matches(required_text, text, preferred_text)
        skill_weight = 0.25 if skills["ratio"] is not None else 0.0
        base_weight = 1.0 - skill_weight
        score = round(base_weight * original["score"]
                      + skill_weight * 100 * (skills["ratio"] or 0))
        positive = "contact" if stage == "precontact" else "high_match"
        negative = "hold" if stage == "precontact" else "potential"
        decision = (positive if score >= threshold else negative) if zero_gate["decision"] == positive else zero_gate["decision"]
        return {"engine": "recruiter_pro_rule_llm_v2", "score": score, "decision": decision,
                "llm_evidence_score": original["score"], "skill_ratio": skills["ratio"],
                "matched_skills": skills["matched"], "missing_skills": skills["missing"],
                "coverage": coverage}
