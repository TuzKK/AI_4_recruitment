"""Stage-independent, job-derived scoring. No profession-specific vocabulary."""
from collections import Counter

from .core import _contains

VERSION = 'generic-v1'


def criterion_weights(criteria):
    if not criteria or len({item['key'] for item in criteria}) != len(criteria):
        raise ValueError('评分项为空或重复')
    counts = Counter(item['category'] for item in criteria)
    base = {'core': 60, 'skill': 30, 'bonus': 10}
    if not set(counts) <= set(base):
        raise ValueError('未知评分类别')
    total = sum(base[c] for c in counts)
    return {item['key']: 100 * base[item['category']] / total / counts[item['category']]
            for item in criteria}


def score_generic(rubric, text, judgement, stage, coverage, threshold):
    if stage not in {'precontact', 'full_resume'} or coverage not in {'partial', 'complete', 'unknown'}:
        raise ValueError('阶段或资料覆盖状态无效')
    if type(threshold) is not int or not 0 <= threshold <= 100:
        raise ValueError('阈值无效')
    if not isinstance(judgement, dict):
        raise ValueError('证据必须为对象')
    claims, reqs = judgement.get('claims'), judgement.get('requirements')
    if not isinstance(claims, dict) or not isinstance(reqs, dict):
        raise ValueError('缺少逐项证据')
    weights = criterion_weights(rubric['criteria'])
    issues, gaps, adjustments, details = [], [], [], {}
    total = known_weight = 0.0
    core_supported = False
    for item in rubric['criteria']:
        key, weight = item['key'], weights[item['key']]
        claim = claims.get(key, {})
        if not isinstance(claim, dict):
            claim = {}
        status, match, strength, quote = (claim.get(k) for k in ('status', 'match', 'strength', 'evidence'))
        unknown = status == 'unknown' and match is None and type(strength) is int and strength == 0 and quote == ''
        known = (status == 'known' and type(match) is int and match in {0, 25, 50, 75, 100}
                 and type(strength) is int and 1 <= strength <= 4 and isinstance(quote, str) and _contains(text, quote))
        if not unknown and not known:
            issues.append(f'{key}: 证据格式或引用无效')
            status, match, strength, quote = 'unknown', None, 0, ''
        if known:
            known_weight += weight
            if strength == 1 and match > 50:
                match = 50
                adjustments.append(f"{item['name']}：仅自述或关键词，最高50分")
            core_supported |= item['category'] == 'core' and strength >= 2 and match >= 50
        effective = match if known else 35
        total += weight * effective / 100
        details[key] = {'weight': round(weight, 4), 'status': status, 'match': match,
                        'strength': strength, 'evidence': quote, 'points': round(weight * effective / 100, 2)}
        if not known or match < 75:
            gaps.append(item['name'])
    failed, unknown_requirements = [], []
    hard = {}
    for item in rubric['requirements']:
        key = item['key']
        claim = reqs.get(key, {})
        if not isinstance(claim, dict):
            claim = {}
        status, quote = claim.get('status'), claim.get('evidence')
        if (status not in {'met', 'failed', 'unknown'} or not isinstance(quote, str) or
                (status == 'unknown' and quote != '') or (status != 'unknown' and not _contains(text, quote))):
            issues.append(f'{key}: 必备条件证据无效')
            status, quote = 'unknown', ''
        hard[key] = {'status': status, 'evidence': quote}
        if status == 'failed':
            failed.append(key)
            gaps.append(item['name'])
        if item['stage'] == 'resume':
            if status == 'unknown':
                unknown_requirements.append(key)
            if status != 'met':
                gaps.append(item['name'])
    reason = judgement.get('reason')
    if not isinstance(reason, str) or not reason.strip():
        issues.append('缺少匹配理由')
        reason = '信息不足，需要核实。'
    value = round(total, 1) if known_weight else None
    evidence_coverage = round(known_weight, 1)
    coarse = stage == 'precontact'
    eligible = (not issues and not failed and core_supported and coverage != 'unknown' and
                evidence_coverage >= (40 if coarse else 80) and
                (coarse or (coverage == 'complete' and not unknown_requirements)))
    if failed:
        decision = 'reject' if coarse else 'not_fit'
    elif issues or coverage == 'unknown':
        decision = 'review'
    elif coarse:
        decision = 'contact' if eligible and value is not None and value >= threshold else 'hold'
    elif coverage != 'complete' or unknown_requirements or evidence_coverage < 80:
        decision = 'review'
    elif eligible and value is not None and value >= threshold:
        decision = 'high_match'
    else:
        decision = 'potential' if value is not None and value >= 50 else 'not_fit'
    return {'score': value, 'decision': decision, 'evidence_coverage': evidence_coverage,
            'coverage': coverage, 'threshold_eligible': bool(eligible), 'breakdown': details,
            'requirements': hard, 'reason': reason.strip()[:160], 'gaps': list(dict.fromkeys(gaps)),
            'issues': issues, 'rule_adjustments': adjustments, 'scoring_version': VERSION}
