"""
Skill matching — the one scoring component that owns a dependency.

Everything here needs the controlled vocabulary, and nothing else in Agent 3
does. That is the seam the split follows.

The vocabulary arrives by constructor injection, the same contract Agent 2 now
uses, so a test can hand this class a five-word index instead of standing up an
agent that loads a 679-skill file and an ML model to check that "Java" does not
match "JavaScript".

This class deliberately knows nothing about `CVProfile` or `JobPosting`: it
takes and returns skill names. Its caller does the unpacking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class SkillMatch:
    """Skill matching results"""

    matched_skills: List[str]
    missing_skills: List[str]
    extra_skills: List[str]
    match_ratio: float


class SkillMatcher:
    """Resolves skills to the controlled vocabulary and scores the overlap."""

    def __init__(self, skills_index: Optional[Dict[str, str]] = None):
        """
        Args:
            skills_index: {alias_lower: Canonical}. Injected rather than loaded,
                so tests need no vocabulary file and there is exactly one loader
                (`src/core/vocabulary.py`) in the codebase.
        """
        self.skills_index: Dict[str, str] = skills_index or {}

    # -- resolution ------------------------------------------------------

    def normalize(self, skills: List[str]) -> List[str]:
        """
        Resolve skill names to their canonical form.

        The vocabulary is consulted before punctuation is stripped, not after.
        Stripping first destroyed 16 index keys and made six canonical skills
        unreachable by their own name -- .NET normalized to "net", which matches
        nothing, so it passed through as the literal string. T-SQL, Monday.com,
        Outreach.io, Stand-ups and Non-Conformance Management failed the same
        way. The stripped form is still tried as a fallback, so inputs the
        index does not carry verbatim ("node.js" against a "nodejs" alias)
        still resolve.
        """
        normalized = []

        for skill in skills:
            cleaned = skill.lower().strip()

            canonical = self.canonical(cleaned)
            if canonical:
                normalized.append(canonical)
                continue

            # Fall back to the punctuation-stripped form.
            stripped = cleaned.replace(".", "").replace("-", " ")
            normalized.append(self.canonical(stripped) or stripped)

        return normalized

    def canonical(self, skill: str) -> Optional[str]:
        """
        Resolve one skill to its canonical name.

        One dict lookup against the alias index built at load time, instead of
        the previous linear scan over the whole vocabulary per skill. That scan
        ran once per skill per job -- so at 800 jobs it was the hot path -- and
        it was also where A0 lived. See `src/core/vocabulary.build_alias_index`.
        """
        if not self.skills_index:
            return None
        return self.skills_index.get(skill.lower())

    # -- matching --------------------------------------------------------

    def find_matches(self, cv_skills: Set[str], job_skills: Set[str]) -> List[str]:
        """
        Find which of job_skills the CV covers.

        Both sides have already been resolved to canonical names by
        `normalize`, so a direct set membership test is the match. There used to
        be a ~45-key synonym dict rebuilt as a local literal on every call --
        once per job, plus once per missing skill -- which made it tens of
        thousands of reconstructions per upload. It was also unreachable: its
        keys and aliases are lowercase, while 667 of the 669 canonical names
        carry uppercase, so the comparison could never fire for any skill the
        vocabulary recognised. The two cases it did cover (devops, ai) were
        genuine vocabulary gaps and are now canonical entries in skills.json.

        Partial credit is granted on whole tokens, not raw substrings. The
        previous rule was `job_skill in cv_skill or cv_skill in job_skill`,
        which credited any pair sharing a character run of four or more --
        "Java" against "JavaScript", "Git" against "GitHub Actions", "SQL"
        against "MySQL", and ".NET" reduced to "net" against the "net" inside
        "PeNETration Testing". Twenty-nine such collisions exist among the 669
        canonical names.

        Requiring the job skill's tokens to be a subset of the CV skill's
        tokens removes all of those while keeping the cases where one skill
        genuinely contains the other as a named concept: "Communication"
        against "Written Communication" still matches, because "communication"
        is a whole token of it.
        """
        matches = []
        cv_token_sets = [(s, self.tokens(s)) for s in cv_skills]

        for job_skill in job_skills:
            # Direct match on canonical names
            if job_skill in cv_skills:
                matches.append(job_skill)
                continue

            job_tokens = self.tokens(job_skill)
            if not job_tokens:
                continue

            for _cv_skill, cv_tokens in cv_token_sets:
                if job_tokens < cv_tokens:
                    matches.append(job_skill)
                    break

        return matches

    def has_match(self, skill: str, cv_skills: Set[str]) -> bool:
        """Check if a skill has a match in CV skills"""
        return len(self.find_matches(cv_skills, {skill})) > 0

    @staticmethod
    def tokens(skill: str) -> frozenset:
        """Split a skill into comparable whole tokens, ignoring punctuation."""
        return frozenset(t for t in re.split(r"[^a-z0-9+#]+", skill.lower()) if t)

    # -- scoring ---------------------------------------------------------

    def match(
        self,
        cv_skills: List[str],
        required_skills: List[str],
        preferred_skills: List[str],
    ) -> SkillMatch:
        """
        Score skill matching between CV and job with enhanced precision

        Uses fuzzy matching, synonym detection, and weighted scoring
        """
        # Bound to new names rather than rebinding the parameters, which were
        # declared List[str] and then held sets from here down. Everything
        # below is set logic, so the sets are what the names should say.
        cv: Set[str] = set(self.normalize(cv_skills))
        required: Set[str] = set(self.normalize(required_skills))
        preferred: Set[str] = set(self.normalize(preferred_skills))

        # Sorted throughout: these lists were built with list(set(...)), so they
        # reordered between process restarts and extra_skills[:10] returned a
        # different ten skills each time. Same defect as the one already fixed
        # in extract_keywords.
        matched_required = self.find_matches(cv, required)
        matched_preferred = self.find_matches(cv, preferred)
        matched_skills = sorted(set(matched_required + matched_preferred))

        # Find gaps
        missing_required = sorted(s for s in required if not self.has_match(s, cv))
        missing_preferred = sorted(s for s in preferred if not self.has_match(s, cv))

        # Extra skills candidate has
        extra_skills = sorted(cv - required - preferred)

        # Calculate match ratio with enhanced precision
        total_required = len(required) or 1
        total_preferred = len(preferred) or 0

        # Weighted ratio: required skills are critical (85%), preferred are bonus (15%)
        required_match_ratio = len(matched_required) / total_required
        preferred_match_ratio = (
            len(matched_preferred) / max(total_preferred, 1) if total_preferred > 0 else 0
        )

        match_ratio = (required_match_ratio * 0.85) + (preferred_match_ratio * 0.15)

        # Penalty for missing critical required skills.
        #
        # Against `required`, the normalized set -- not `required_skills`, the
        # raw list, which is what this compared until the sets were given their
        # own names. `missing_required` is derived from the set, so measuring it
        # against the list compared two different denominators: a job listing
        # "React" and "ReactJS" counted two requirements and could only ever
        # miss one, putting the 50% penalty out of reach.
        #
        # No score moves on the shipped corpus -- 0 of 800 jobs have a
        # required_skills list that normalization shortens, measured. It
        # matters for jobs created through POST /jobs, where the skill list is
        # whatever the caller typed.
        if len(missing_required) > len(required) * 0.5:  # Missing more than 50%
            match_ratio *= 0.7  # 30% penalty

        return SkillMatch(
            matched_skills=matched_skills,
            missing_skills=missing_required + missing_preferred,
            extra_skills=extra_skills[:10],  # Limit to top 10
            match_ratio=min(1.0, match_ratio),
        )
