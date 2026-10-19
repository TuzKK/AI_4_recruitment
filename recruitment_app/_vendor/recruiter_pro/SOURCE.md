# Recruiter Pro component provenance

- Upstream: https://github.com/Sharawey74/Recruiter-Pro
- Audited revision: `daf160bbe97e269846a78e53b5c6f5d2affeb0bf`
- License: MIT; original copyright notice is retained in `LICENSE`.
- Copied without editing: `src/agents/scoring/skill_matcher.py` and `data/dictionaries/skills.json`.

This is a specialized resume screening project. Its independent `SkillMatcher`
normalizes aliases, requires whole-token matches, and separates required from
preferred skills. These are reused by `recruitment_app.shadow_matching` with
additional Chinese aliases. The upstream application, fixed role weights,
title/education scoring, and ML model are not reused: they do not match this
dynamic Chinese recruitment workflow or the API-only deployment requirement.

The vendored code is a deterministic rule component. The only model in this
application is the hosted DashScope Qwen LLM configured in `llm.py`.
