"""Local, API-only two-stage resume evaluation primitives.

The proxy card is intentionally a short, deterministic excerpt. It cannot
stand in for a real BOSS precontact snapshot when reporting online recall.
"""

from __future__ import annotations

import argparse
import re
import json
import hashlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

import httpx

from .core import _contains
from .core import validate_rubric

ORDERED_TIERS = ("strong_match", "borderline", "hard_negative", "ordinary_negative", "unrelated")
TIERS = ORDERED_TIERS + ("private_rejected",)


def redact_contacts(text: str) -> str:
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[EMAIL]", text, flags=re.I)
    text = re.sub(r"(?<!\d)(?:\+?86[\s-]?)?1[3-9]\d{9}(?!\d)", "[PHONE]", text)
    return text


def make_proxy_card(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("简历正文为空")
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        line = re.split(r"\[PHONE\]|\[EMAIL\]|电话|手机|邮箱|电子邮件|住址|地址|婚姻|籍贯|民族|年\s*龄|姓\s*名", line, maxsplit=1, flags=re.I)[0].strip()
        if not line:
            continue
        if re.search(r"(?:省|市|区).{0,20}(?:路|街|号)", line):
            continue
        if "求职意向" in line:
            line = line[line.index("求职意向"):]
        if len(line) <= 8 and not re.search(r"工作|项目|教育|学历|技能|求职|意向", line):
            continue  # likely a standalone name
        lines.append(line)
    intro = next((line[:40] for line in lines if "求职意向" in line), "")
    education = next((line[:60] for line in lines if re.search(r"本科|学士|硕士|博士", line)), "")
    start = next((i for i, line in enumerate(lines) if re.search(r"^(?:工作|实习|项目|职业|任职).{0,4}经历", line)), None)
    if start is not None:
        heading_remainder = re.sub(r"^(?:工作|实习|项目|职业|任职).{0,4}经历\s*[:：]?\s*", "", lines[start])
        work = ([heading_remainder] if heading_remainder else []) + [line for line in lines[start + 1:start + 9]
                if not re.search(r"^(?:教育|技能|获奖|证书|课外|社会实践|个人技能)", line)]
    else:
        work = [line for line in lines if re.search(r"负责|参与|使用|开发|实施|维护|配置|设计|担任", line)][:7]
    # This is an offline proxy, not an online capture: retain technical evidence
    # even when PDF section order puts it after many introductory lines.
    signals = r"SQL|Python|JavaScript|字段映射|数据接入|数据清洗|实例导入|数据建模|本体|知识图谱|FastAPI|LangGraph"
    technical = sorted((line for line in lines if re.search(signals, line, re.I)),
                       key=lambda line: -len(re.findall(signals, line, re.I)))
    selected = [part for part in (intro[:25], education[:45]) if part]
    for line in technical + work:
        fragment = line[:65]
        if fragment not in selected:
            selected.append(fragment)
        if len(" ".join(selected)) >= 200:
            break
    card = " ".join(selected)[:200].strip()
    if not card:
        card = " ".join(lines)[:200].strip()
    if not card:
        raise ValueError("无法从正文形成代理卡片")
    return card


def _has_technical_context(text):
    # This only distinguishes adjacent technical work from distant work; it never qualifies anyone.
    pattern = r"软件开发|数据工程|数据库|数据仓库|数据平台|大数据|前端开发|程序开发|本体建模|知识图谱|字段映射|数据接入|数据清洗|\b(?:SQL|Python|JavaScript|Java|Hadoop|Spark)\b|C\+\+"
    for match in re.finditer(pattern, text, re.I):
        before = re.split(r"[。；;\n]|但是|不过|然而|但", text[:match.start()])[-1]
        after = text[match.end():match.end() + 6]
        if not re.search(r"未|没有|不涉及|不从事|不使用|不懂|无.*经验|缺乏", before + after):
            return True
    return False


def _ontology_competencies(rubric, levels):
    """Recognize the ontology-delivery requirements from JD quotes, never sample labels."""
    patterns = {"modeling": r"本体|对象.*属性|对象.*关系",
                "sql": r"\bSQL\b", "coding": r"Python|JavaScript",
                "delivery": r"软件实施|系统实施|项目交付|数据接入"}
    selected = {}
    for role, pattern in patterns.items():
        candidates = [item for item in rubric["criteria"] if item["category"] != "bonus" and
                      re.search(pattern, item["jd_quote"], re.I)]
        if len(candidates) != 1:
            return None
        selected[role] = candidates[0]["key"]
    if len(set(selected.values())) != 4:
        return None
    minima = {"modeling": (2, 2), "sql": (2, 3), "coding": (1, 2), "delivery": (3, 3)}
    return {role: levels[key]["level"] >= minima[role][0] and levels[key]["fit"] >= minima[role][1]
            for role, key in selected.items()}


def score_detailed(rubric: dict, text: str, judgement: dict, stage: str,
                   coverage: str, threshold: int) -> dict:
    """Check LLM citations, then score evidence strength and work relevance."""
    if stage not in {"precontact", "full_resume"} or coverage not in {"partial", "complete", "unknown"}:
        raise ValueError("筛选阶段或覆盖状态无效")
    if type(threshold) is not int or not 0 <= threshold <= 100:
        raise ValueError("阈值无效")
    if not isinstance(judgement, dict):
        raise TypeError("模型结果必须为对象")
    claims = judgement.get("claims")
    requirements = judgement.get("requirements")
    if not isinstance(claims, dict) or not isinstance(requirements, dict):
        raise ValueError("模型未返回逐项证据")
    issues, breakdown, levels, citations, gaps = [], {}, {}, {}, []
    rule_adjustments = []
    total = 0.0
    for item in rubric["criteria"]:
        key = item["key"]
        claim = claims.get(key)
        if not isinstance(claim, dict):
            claim = {}
        level, fit, quote = claim.get("level"), claim.get("fit"), claim.get("evidence")
        valid = (type(level) is int and 0 <= level <= 4 and type(fit) is int and 0 <= fit <= 4
                 and isinstance(quote, str) and ((level == 0 and fit == 0 and not quote) or
                                                  (level > 0 and fit > 0 and _contains(text, quote))))
        if not valid:
            issues.append(f"{key}: 证据或相关性无效")
            level, fit, quote = 0, 0, ""
        elif (level > 1 and re.search(r"熟悉|掌握|了解", quote) and not re.search(
                r"负责|使用|参与|完成|实现|开发|设计|搭建|构建|编写|优化|调试|部署|交付|建立|维护", quote)):
            level = 1
            rule_adjustments.append(f"{item['name']}：仅技能自述，证据强度上限为1")
        points = round(item["weight"] * level * fit / 16, 2)
        breakdown[key] = points
        levels[key] = {"level": level, "fit": fit}
        if quote:
            citations[key] = quote
        else:
            gaps.append(item["name"])
        total += points
    hard_failed = False
    hard_unknown = False
    for item in rubric["requirements"]:
        claim = requirements.get(item["key"], {})
        status = claim.get("status") if isinstance(claim, dict) else None
        quote = claim.get("evidence") if isinstance(claim, dict) else None
        if (status in {"unknown", "failed"} and "专业" in item["name"] and
                "相关" in item["jd_quote"] and "计算机" in item["jd_quote"]):
            # Explicit related-computing-degree taxonomy, applied equally to every candidate.
            majors = ("计算机科学与技术", "软件工程", "数据科学", "信息管理", "通信工程",
                      "信息工程", "电子信息工程", "人工智能", "数字媒体技术")
            for other in requirements.values():
                if not isinstance(other, dict) or other.get("status") != "met":
                    continue
                education_quote = other.get("evidence", "")
                if not isinstance(education_quote, str) or not _contains(text, education_quote):
                    continue
                compact = re.sub(r"\s+", "", education_quote)
                if re.search(r"本科|学士|硕士|博士", compact) and any(
                    re.search(r"专业[:：]?" + re.escape(major), compact) or
                    re.search(re.escape(major) + r"[（(]?(?:本科|学士|硕士|博士)", compact)
                    for major in majors
                ):
                    status, quote = "met", education_quote
                    rule_adjustments.append(f"{item['name']}：教育原文符合相关计算机工科专业规则")
                    break
        if status not in {"met", "failed", "unknown"} or not isinstance(quote, str) or (
            status != "unknown" and not _contains(text, quote)
        ):
            issues.append(f"{item['key']}: 硬条件证据无效")
            status = "unknown"
        if item["stage"] == "resume":
            hard_failed |= status == "failed"
            hard_unknown |= status == "unknown"
            if status != "met":
                gaps.append(item["name"])
    score = round(total, 1)
    core = any(levels[i["key"]]["level"] >= 1 and levels[i["key"]]["fit"] >= 2
               for i in rubric["criteria"] if i["category"] == "core")
    skill = any(levels[i["key"]]["level"] >= 1 and levels[i["key"]]["fit"] >= 2
                for i in rubric["criteria"] if i["category"] == "skill")
    raw_score = score
    competency_gates = _ontology_competencies(rubric, levels) if stage == "full_resume" else None
    qualification_band = None
    if competency_gates is not None:
        if all(competency_gates.values()) and not hard_failed and not hard_unknown:
            qualification_band, score = "qualified", round(75 + .25 * raw_score, 1)
        elif competency_gates["sql"] and competency_gates["coding"] and not hard_failed:
            qualification_band, score = "potential", round(50 + .24 * raw_score, 1)
        elif _has_technical_context(text):
            qualification_band, score = "related_gap", round(20 + .29 * raw_score, 1)
        else:
            qualification_band, score = "unrelated", round(.19 * raw_score, 1)
        names = {"modeling": "建模概念实践", "sql": "SQL实操", "coding": "Python/JavaScript基础", "delivery": "实施交付实践"}
        gaps.extend(names[key] for key, passed in competency_gates.items() if not passed)
    reason = judgement.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        issues.append("缺少简短理由")
        reason = "证据不足，需要人工核查。"
    elif len(reason.strip()) > 160:
        reason = reason.strip()[:159] + "…"
    model_gaps = judgement.get("gaps", [])
    if not isinstance(model_gaps, list) or any(not isinstance(x, str) for x in model_gaps):
        issues.append("缺口列表无效")
        model_gaps = []
    evidence_gate = (core or skill) if stage == "precontact" else (core and skill)
    if competency_gates is not None:
        evidence_gate = all(competency_gates.values())
    threshold_eligible = bool(evidence_gate and not issues and not hard_failed
                              and coverage != "unknown" and (stage == "precontact" or
                              (coverage == "complete" and not hard_unknown)))
    if hard_failed:
        decision = "reject" if stage == "precontact" else "not_fit"
    elif issues or coverage == "unknown":
        decision = "review"
    elif stage == "precontact":
        decision = "contact" if evidence_gate and score >= threshold else "hold"
    elif coverage != "complete":
        decision = "review"
    elif competency_gates is not None:
        if hard_unknown and qualification_band in {"qualified", "potential"}:
            decision = "review"
        elif qualification_band == "qualified" and score >= threshold:
            decision = "high_match"
        else:
            decision = "potential" if qualification_band in {"qualified", "potential"} else "not_fit"
    elif score < 40 and not core and not skill:
        decision = "not_fit"
    elif hard_unknown:
        decision = "review"
    elif core and skill and score >= threshold:
        decision = "high_match"
    else:
        decision = "potential" if score >= 50 else "not_fit"
    return {"score": score, "decision": decision, "coverage": coverage,
            "threshold_eligible": threshold_eligible,
            "breakdown": breakdown, "levels": levels, "evidence": citations,
            "reason": reason.strip(), "gaps": list(dict.fromkeys(gaps + model_gaps))[:10],
            "issues": issues, "rule_adjustments": rule_adjustments,
            "raw_score": raw_score, "competency_gates": competency_gates,
            "qualification_band": qualification_band}


def summarize_tiers(rows: list[dict]) -> dict:
    scores = {tier: [] for tier in TIERS}
    unscored = []
    for row in rows:
        tier = row.get("tier")
        score = (row.get("fine") or {}).get("score")
        if tier not in scores or type(score) not in (int, float):
            unscored.append(row.get("id"))
        else:
            scores[tier].append(score)
    medians = {tier: median(values) if values else None for tier, values in scores.items()}
    chain = [medians[tier] for tier in ORDERED_TIERS if medians[tier] is not None]
    ordered = all(a is not None and b is not None and a > b for a, b in zip(chain, chain[1:]))
    distant = scores["unrelated"] or scores["ordinary_negative"]
    hard_gap = round(median(scores["hard_negative"]) - median(distant), 1) if scores["hard_negative"] and distant else None
    def percentile(values: list[float], p: float) -> float | None:
        if not values:
            return None
        ordered_values = sorted(values)
        position = (len(values) - 1) * p
        left = int(position)
        fraction = position - left
        return round(ordered_values[left] * (1 - fraction)
                     + ordered_values[min(left + 1, len(values) - 1)] * fraction, 1)

    quantiles = {tier: {"p10": percentile(values, .1), "p90": percentile(values, .9)}
                 for tier, values in scores.items()}
    adjacent_band_gaps = {}
    for upper, lower in zip(ORDERED_TIERS, ORDERED_TIERS[1:]):
        a, b = quantiles[upper]["p10"], quantiles[lower]["p90"]
        adjacent_band_gaps[f"{upper}>{lower}"] = round(a - b, 1) if a is not None and b is not None else None
    order = {tier: i for i, tier in enumerate(ORDERED_TIERS)}
    inversion_ids = []
    for row in rows:
        tier = row.get("tier")
        score = (row.get("fine") or {}).get("score")
        if tier not in order or type(score) not in (int, float):
            continue
        higher = [value for upper in ORDERED_TIERS[:order[tier]] for value in scores[upper]]
        if higher and score >= min(higher):
            inversion_ids.append(row["id"])
    return {"count": {tier: len(values) for tier, values in scores.items()},
            "median": medians, "ordered_medians": ordered,
            "quantiles": quantiles, "adjacent_band_gaps": adjacent_band_gaps,
            "inversion_ids": inversion_ids,
            "hard_unrelated_margin": hard_gap, "unscored": unscored}


def load_local_cases(root: Path) -> list[dict]:
    """Load immutable source labels plus an explicit, auditable review overlay."""
    root = Path(root).resolve()
    dependency_dir = Path(__file__).parent / ".runtime" / "benchmark_deps"
    if dependency_dir.is_dir() and str(dependency_dir) not in sys.path:
        sys.path.insert(0, str(dependency_dir))
    from .benchmark import load_cases
    from matching_eval.samples import load_manifest
    from pypdf import PdfReader

    cases = []
    private_paths = {sample["id"]: root / sample["file"] for sample in load_manifest(root)}
    for case in load_cases(root):
        if case["group"] == "private":
            # Keep PDF extraction identical across application and evaluation accounts.
            case["text"] = "\n".join(page.extract_text() or "" for page in
                                     PdfReader(private_paths[case["id"]]).pages).strip()
            tier = "strong_match" if case["label"] == "high_match" else "private_rejected"
            coarse, fine = ("pass", "pass") if case["label"] == "high_match" else (None, "reject")
        else:
            tier, coarse, fine = "unrelated", "reject", "reject"
        cases.append({**case, "tier": tier, "expected_coarse": coarse, "expected_fine": fine})
    synthetic = root / "synthetic_100"
    manifest = json.loads((synthetic / "manifest.json").read_text(encoding="utf-8"))
    overlay = json.loads((synthetic / "review_labels.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or overlay.get("schema_version") != 1:
        raise ValueError("样本清单版本不支持")
    reviewed = overlay["reviews"]
    ids = {case["id"] for case in cases}
    for sample in manifest["samples"]:
        cid = sample["id"]
        relative = Path(sample["text"])
        path = (synthetic / relative).resolve()
        if cid in ids or not path.is_relative_to(synthetic) or path.suffix.lower() != ".txt":
            raise ValueError(f"样本 ID 或路径无效: {cid}")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != sample["text_sha256"]:
            raise ValueError(f"样本文本哈希变化: {cid}")
        review = reviewed.get(cid)
        if review and (review.get("original") != sample["label"] or not review.get("reason")):
            raise ValueError(f"标签复核记录无效: {cid}")
        if review and (not isinstance(review.get("evidence"), list) or
                       any(not isinstance(quote, str) or not _contains(content.decode("utf-8"), quote)
                           for quote in review["evidence"])):
            raise ValueError(f"标签复核证据不在正文: {cid}")
        tier = review["revised"] if review else sample["label"]
        if tier not in {"strong_match", "borderline", "hard_negative", "ordinary_negative"}:
            raise ValueError(f"样本层级无效: {cid}")
        coarse = sample["expected_coarse"]
        fine = sample["expected_fine"]
        if review and tier != sample["label"]:
            coarse = "reject" if tier == "ordinary_negative" else "pass"
            fine = {"strong_match": "pass", "borderline": "review",
                    "hard_negative": "reject", "ordinary_negative": "reject"}[tier]
        cases.append({"id": cid, "group": "synthetic", "tier": tier,
                      "original_tier": sample["label"], "expected_coarse": coarse,
                      "expected_fine": fine, "review_note": review["reason"] if review else sample.get("review_note", ""),
                      "text": content.decode("utf-8")})
        ids.add(cid)
    if len(manifest["samples"]) != 100 or len(cases) != 118 or set(reviewed) - ids:
        raise ValueError("本地样本数量或复核 ID 与清单不一致")
    stress = json.loads((root / "stress_unrelated.json").read_text(encoding="utf-8"))
    if stress.get("schema_version") != 1 or len(stress.get("samples", [])) != 2:
        raise ValueError("跨领域压力样本清单无效")
    for sample in stress["samples"]:
        cid, text = sample["id"], sample["text"]
        if cid in ids or not isinstance(text, str) or len(text) < 50:
            raise ValueError("跨领域压力样本无效")
        cases.append({"id": cid, "group": "stress", "tier": "unrelated",
                      "expected_coarse": "reject", "expected_fine": "reject", "text": text})
        ids.add(cid)
    return cases


def _cached_judgement(model, cache_dir: Path, rubric: dict, stage: str, text: str) -> dict:
    """Cache remote responses by every input that affects the prompt."""
    envelope = {"version": "detailed-v3-spans", "model": getattr(model, "model", "unknown"),
                "stage": stage, "rubric": rubric, "text": text}
    digest = hashlib.sha256(json.dumps(envelope, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    path = cache_dir / f"{digest}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        restore = getattr(model, "_restore_spans", None)
        return restore(cached, text) if callable(restore) else cached
    for attempt in range(3):
        try:
            judgement = model.detailed_evidence(stage, rubric, text)
            break
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {429, 500, 502, 503} or attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except (httpx.ConnectError, httpx.ReadTimeout):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(judgement, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return judgement


def repair_judgement(model, cache_dir, rubric, stage, text, judgement, issues):
    envelope = {"version": "citation-repair-v3-spans", "model": getattr(model, "model", "unknown"),
                "rubric": rubric, "stage": stage, "text": text, "judgement": judgement, "issues": issues}
    digest = hashlib.sha256(json.dumps(envelope, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    path = Path(cache_dir) / f"repair-{digest}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        restore = getattr(model, "_restore_spans", None)
        return restore(cached, text) if callable(restore) else cached
    corrected = model.repair_detailed_evidence(stage, rubric, text, judgement, issues)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(corrected, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return corrected


def _cached_rubric(model, cache_dir: Path, job: str) -> dict:
    envelope = {"version": "rubric-v1", "model": getattr(model, "model", "unknown"), "job": job}
    digest = hashlib.sha256(json.dumps(envelope, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    path = cache_dir / f"rubric-{digest}.json"
    if path.exists():
        return validate_rubric(job, json.loads(path.read_text(encoding="utf-8")))
    rubric = validate_rubric(job, model.rubric(job))
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(rubric, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return rubric


def _expected_decision(decision: str, stage: str) -> str:
    if stage == "precontact":
        return {"contact": "pass", "hold": "reject", "reject": "reject", "review": "review"}[decision]
    return {"high_match": "pass", "potential": "review", "not_fit": "reject", "review": "review"}[decision]


def _stage_metrics(rows: list[dict], stage: str) -> dict:
    key = "coarse" if stage == "precontact" else "fine"
    expected_key = "expected_coarse" if stage == "precontact" else "expected_fine"
    eligible = [row for row in rows if row.get(expected_key) in {"pass", "review", "reject"}]
    checked, mismatches = 0, []
    incorrect = 0
    tp = fp = fn = 0
    for row in eligible:
        result = row.get(key, {})
        if "decision" not in result:
            mismatches.append(row["id"])
            continue
        checked += 1
        predicted = _expected_decision(result["decision"], stage)
        actual = row[expected_key]
        if predicted != actual:
            mismatches.append(row["id"])
            incorrect += 1
        tp += predicted == "pass" and actual == "pass"
        fp += predicted == "pass" and actual != "pass"
        fn += predicted != "pass" and actual == "pass"
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"expected": len(eligible), "evaluated": checked, "matching_decisions": checked - incorrect,
            "mismatch_ids": mismatches, "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3), "weighted_75_25": round(.75 * recall + .25 * precision, 3)}


def _topk_yield(rows: list[dict], k: int) -> dict:
    ranked = sorted((r for r in rows if r.get("coarse", {}).get("decision") == "contact"),
                    key=lambda r: (-r["coarse"]["score"], r["id"]))[:k]
    strong = sum(r["tier"] == "strong_match" for r in ranked)
    return {"quota": k, "selected": len(ranked), "strong_match": strong,
            "share": round(strong / len(ranked), 3) if ranked else None}


def pipeline_metrics(rows):
    labeled = [row for row in rows if row.get("expected_fine") in {"pass", "review", "reject"}]
    tp = fp = fn = tn = 0
    mismatches, missing = [], []
    for row in labeled:
        if any("decision" not in row.get(stage, {}) for stage in ("coarse", "fine")):
            missing.append(row["id"])
            continue
        predicted = row["coarse"]["decision"] == "contact" and row["fine"]["decision"] == "high_match"
        expected = row["expected_fine"] == "pass"
        tp += predicted and expected
        fp += predicted and not expected
        fn += not predicted and expected
        tn += not predicted and not expected
        if predicted != expected:
            mismatches.append(row["id"])
    evaluated = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    return {"status": "incomplete" if missing else "complete", "expected": len(labeled),
            "evaluated": evaluated, "correct": tp + tn, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 3), "recall": round(recall, 3),
            "weighted_75_25": round(.75 * recall + .25 * precision, 3),
            "accuracy": round((tp + tn) / evaluated, 3) if evaluated else None,
            "mismatch_ids": mismatches, "missing_ids": missing}


def recommend_threshold(rows: list[dict], stage: str) -> dict:
    """Exploratory threshold search on fixed evidence; never changes online defaults."""
    if stage not in {"precontact", "full_resume"}:
        raise ValueError("筛选阶段无效")
    key = "coarse" if stage == "precontact" else "fine"
    expected_key = "expected_coarse" if stage == "precontact" else "expected_fine"
    labeled = [row for row in rows if row.get(expected_key) in {"pass", "reject", "review"}]
    if not labeled or any(type(row.get(key, {}).get("score")) not in (int, float)
                          or type(row.get(key, {}).get("threshold_eligible")) is not bool for row in labeled):
        return {"status": "incomplete_data"}
    if not any(row[expected_key] == "pass" for row in labeled):
        return {"status": "insufficient_positives"}
    best, winner = None, None
    for threshold in range(101):
        selected = [row for row in labeled if row[key]["threshold_eligible"] and row[key]["score"] >= threshold]
        if not selected:
            continue
        ids = {row["id"] for row in selected}
        tp = sum(row["id"] in ids and row[expected_key] == "pass" for row in labeled)
        fp = sum(row["id"] in ids and row[expected_key] != "pass" for row in labeled)
        fn = sum(row["id"] not in ids and row[expected_key] == "pass" for row in labeled)
        precision = tp / (tp + fp)
        recall = tp / (tp + fn)
        if stage == "precontact":
            top = sorted(selected, key=lambda row: (-row[key]["score"], row["id"]))[:10]
            if sum(row["tier"] == "strong_match" for row in top) / len(top) < .10:
                continue
        weighted = .75 * recall + .25 * precision
        rank = (weighted, recall if stage == "precontact" else precision, precision if stage == "precontact" else recall, threshold)
        if best is None or rank > best:
            best = rank
            winner = {"status": "exploratory", "threshold": threshold, "selected": len(selected),
                      "precision": round(precision, 3), "recall": round(recall, 3),
                      "weighted_75_25": round(weighted, 3)}
    return winner or {"status": "no_threshold_meets_constraints"}


def evaluate_local_cases(job: str, cases: list[dict], model, cache_dir: Path,
                         *, coarse_threshold: int = 30, fine_threshold: int = 75,
                         on_progress=None, workers: int = 1) -> dict:
    """Evaluate all full texts diagnostically; only coarse pass rows appear in UI."""
    cache_dir = Path(cache_dir)
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("评测并发数必须为1至8")
    rubric = _cached_rubric(model, cache_dir, job)
    rows = []
    def evaluate_one(case):
        text = redact_contacts(case["text"])
        row = {key: case.get(key) for key in ("id", "group", "tier", "original_tier",
                                            "expected_coarse", "expected_fine", "review_note")}
        row["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if not 0 < len(text) <= 30000:
            row["coarse"] = row["fine"] = {"error": "text_length"}
        else:
            for stage, key, source, coverage, threshold in (
                ("precontact", "coarse", make_proxy_card(text), "partial", coarse_threshold),
                ("full_resume", "fine", text, "complete", fine_threshold),
            ):
                try:
                    judgement = _cached_judgement(model, cache_dir, rubric, stage, source)
                    row[key] = score_detailed(rubric, source, judgement, stage, coverage, threshold)
                    if row[key]["issues"] and callable(getattr(model, "repair_detailed_evidence", None)):
                        judgement = repair_judgement(model, cache_dir, rubric, stage, source,
                                                     judgement, row[key]["issues"])
                        row[key] = score_detailed(rubric, source, judgement, stage, coverage, threshold)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in {401, 403}:
                        raise
                    row[key] = {"error": f"HTTP_{exc.response.status_code}"}
                except Exception as exc:  # one failed sample must remain visible in report
                    row[key] = {"error": type(exc).__name__}
        row["show_in_web"] = row["coarse"].get("decision") == "contact"
        return row
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for index, row in enumerate(executor.map(evaluate_one, cases), 1):
            rows.append(row)
            if on_progress:
                on_progress(index, len(cases), row["id"])
    complete = all("decision" in row.get(stage, {}) for row in rows for stage in ("coarse", "fine"))
    return {"status": "complete" if complete else "incomplete", "model": getattr(model, "model", "unknown"),
            "prompt_version": "detailed-v3-spans", "job_title": rubric["title"],
            "rubric": rubric, "proxy_card_limit": 200, "coarse_threshold": coarse_threshold,
            "fine_threshold": fine_threshold, "rows": rows,
            "tiers": summarize_tiers(rows),
            "coarse_metrics": _stage_metrics(rows, "precontact"),
            "fine_metrics": _stage_metrics(rows, "full_resume"),
            "pipeline_metrics": pipeline_metrics(rows),
            "scoring_version": "ontology-competency-v1",
            "suggested_coarse": recommend_threshold(rows, "precontact"),
            "suggested_fine": recommend_threshold(rows, "full_resume"),
            "topk": [_topk_yield(rows, k) for k in (10, 20)]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate local resumes with hosted Qwen API only")
    parser.add_argument("--sample-root", type=Path, default=Path("Samples_for_optimization"))
    parser.add_argument("--output", type=Path, default=Path("recruitment_app/.runtime/local_evals/baseline.json"))
    parser.add_argument("--coarse-threshold", type=int, default=30)
    parser.add_argument("--fine-threshold", type=int, default=75)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    args = parser.parse_args(argv)
    from .llm import JobModel

    model = JobModel.from_environment()
    job = (args.sample_root / "recruitment_request.txt").read_text(encoding="utf-8")
    cases = load_local_cases(args.sample_root)

    def progress(done, total, _candidate_id):
        if done % 5 == 0 or done == total:
            print(f"已评测 {done}/{total}", flush=True)

    report = evaluate_local_cases(job, cases, model, args.output.parent / "cache",
                                  coarse_threshold=args.coarse_threshold,
                                  fine_threshold=args.fine_threshold,
                                  on_progress=progress, workers=args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("tiers", "coarse_metrics", "fine_metrics", "suggested_coarse", "suggested_fine", "topk")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
