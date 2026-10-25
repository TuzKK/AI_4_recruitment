"""Sequential, resumable recruitment run with send-before-record safeguards."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import safe_title, score_evidence, validate_rubric
from .shadow_matching import ShadowMatcher
from .messages import MessageComposer
from .boss import CandidateUnavailable, GreetingNotSent


class RunStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _path(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not uuid.UUID(run_id):
            raise ValueError("运行 ID 无效")
        return self.root / "runs" / f"{run_id}.json"

    def _write(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def create(self, job: str, quota: int, coarse: int, fine: int, message: str, message_mode: str = 'fixed',
               scoring_version: str = 'legacy-v3', rate_limits=None) -> str:
        rate_limits = rate_limits if rate_limits is not None else {'request_seconds': 5, 'greet_seconds': 20}
        if not isinstance(rate_limits, dict):
            raise ValueError('请求频率配置格式无效')
        r, g = rate_limits.get('request_seconds'), rate_limits.get('greet_seconds')
        if type(r) not in (int, float) or not 5 <= r <= 30 or type(g) not in (int, float) or not 20 <= g <= 60:
            raise ValueError('请求间隔须为5至30秒，打招呼间隔须为20至60秒')
        if len(job.strip()) < 20 or type(quota) is not int or not 1 <= quota <= 100:
            raise ValueError("请输入完整招聘需求和 1 至 100 的目标人数")
        if any(type(x) is not int or not 0 <= x <= 100 for x in (coarse, fine)):
            raise ValueError("阈值必须为 0 至 100")
        if message_mode not in {'fixed', 'llm'}:
            raise ValueError('消息模式必须为fixed或llm')
        if scoring_version not in {'legacy-v3', 'generic-v1'}:
            raise ValueError('未知评分版本')
        if not isinstance(message, str) or (message_mode == 'fixed' and not 1 <= len(message.strip()) <= 500):
            raise ValueError("首条消息须为 1 至 500 字")
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone(timedelta(hours=8)))
        data = {"id": run_id, "created_at": now.isoformat(), "status": "queued", "job": job,
                "quota": quota, "coarse_threshold": coarse, "fine_threshold": fine,
                "message": message.strip(), "message_mode": message_mode,
                "scoring_version": scoring_version, "rate_limits": rate_limits,
                "title": None, "rubric": None, "candidates": {},
                "contacted": 0, "error": None}
        with self.lock:
            self._write(self._path(run_id), data)
        return run_id

    def get(self, run_id: str) -> dict:
        with self.lock:
            return json.loads(self._path(run_id).read_text(encoding="utf-8"))

    def recover(self) -> None:
        """A restart never replays a possibly dispatched write."""
        with self.lock:
            for path in (self.root / "runs").glob("*.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["status"] in {"running", "stop_requested"}:
                    data["status"] = "paused"
                for candidate in data["candidates"].values():
                    if candidate.get("state") in {"greet_pending", "message_pending"}:
                        candidate['greeting_attempted'] = True
                        candidate["state"] = "needs_review"
                self._write(path, data)

    def update(self, run_id: str, **fields) -> dict:
        with self.lock:
            data = self.get(run_id)
            data.update(fields)
            self._write(self._path(run_id), data)
            return data

    def candidate(self, run_id: str, candidate_id: str, **fields) -> None:
        with self.lock:
            data = self.get(run_id)
            data["candidates"].setdefault(candidate_id, {}).update(fields)
            data["contacted"] = sum(bool(c.get("greet_verified") or c.get("message_verified") or
                                        c.get("state") == "sent_verified") for c in data["candidates"].values())
            self._write(self._path(run_id), data)

    def export(self, run_id: str) -> Path:
        with self.lock:
            data = self.get(run_id)
            date = data["created_at"][:10]
            folder = self.root / "results" / f"{safe_title(data['title'])}_{date}"
            folder.mkdir(parents=True, exist_ok=True)
            output = folder / "qualified_contacted.txt"
            rows = {}
            if output.exists():
                for line in output.read_text(encoding="utf-8").splitlines():
                    parts = line.split("｜")
                    if len(parts) >= 3:
                        rows[parts[1]] = line
            for cid, candidate in data["candidates"].items():
                if ((candidate.get("message_verified") or candidate.get("state") == "sent_verified")
                        and candidate.get("fine", {}).get("decision") == "high_match"):
                    safe_name = str(candidate["name"]).replace("｜", " ").replace("\r", " ").replace("\n", " ")
                    rows[cid] = f"{safe_name}｜{cid}｜{candidate['fine']['score']}"
            temporary = output.with_suffix(".tmp")
            temporary.write_text("\n\n".join(rows.values()) + ("\n" if rows else ""), encoding="utf-8")
            os.replace(temporary, output)
            return output


def _assess(model, stage, rubric, text, coverage, threshold):
    if callable(getattr(model, "assess", None)):
        return {}, model.assess(stage, rubric, text, coverage, threshold)
    # Retain compatibility with existing provider adapters using the legacy protocol.
    judgement = model.evidence(stage, rubric, text)
    return judgement, score_evidence(rubric, text, judgement, stage, coverage, threshold)


def _stopped(store, run_id):
    if store.get(run_id)['status'] == 'stop_requested':
        store.update(run_id, status='paused')
        return True
    return False


def _used(data):
    return sum(bool(c.get('greeting_attempted') or c.get('greet_verified') or
                    c.get('message_verified') or c.get('state') == 'sent_verified')
               for c in data['candidates'].values())


def _contact(store, run_id, cid, model, boss, rubric):
    data = store.get(run_id)
    candidate = data['candidates'][cid]
    if candidate.get('message_verified') or candidate.get('state') == 'sent_verified':
        return True
    if candidate.get('state') in {'needs_review', 'greet_pending', 'message_pending'}:
        return False  # Never replay an uncertain write.
    if not candidate.get('greet_verified'):
        if _used(data) >= data['quota']:
            return False
        if data.get('message_mode', 'fixed') == 'llm':
            try:
                outreach = MessageComposer(model).prepare(
                    data['job'], candidate['coarse_text'], candidate['coarse'].get('gaps', []),
                    candidate.get('outreach'),
                    save=lambda value: store.candidate(run_id, cid, outreach=value))
            except Exception as exc:
                store.candidate(run_id, cid, message_error=f'消息生成/复核异常：{type(exc).__name__}')
                store.update(run_id, status='paused', error='消息生成/复核失败，请检查 API 后恢复')
                return False
            store.candidate(run_id, cid, outreach=outreach, message_error=None)
            if outreach['status'] != 'approved':
                store.candidate(run_id, cid, state='message_rejected')
                return False
        else:
            outreach = {'mode': 'fixed', 'status': 'fixed',
                        'message': data['message'].replace('{职位名称}', rubric['title']),
                        'reason': '使用用户设定的固定消息'}
            store.candidate(run_id, cid, outreach=outreach)
        if _stopped(store, run_id):
            return False
        store.candidate(run_id, cid, state='greet_pending', greeting_attempted=False,
                        fine={}, fine_completed=False)
        try:
            greeted = boss.greet(cid)
        except CandidateUnavailable as exc:
            store.candidate(run_id, cid, state='candidate_unavailable', greeting_attempted=False,
                            greeting_error=str(exc)[:300])
            return False
        except GreetingNotSent as exc:
            store.candidate(run_id, cid, state='greet_not_sent', greeting_attempted=False,
                            greeting_error=str(exc)[:300])
            store.update(run_id, status='paused', error=f'打招呼未发送：{str(exc)[:240]}')
            return False
        except Exception as exc:
            store.candidate(run_id, cid, greeting_error=f'{type(exc).__name__}: {str(exc)[:240]}')
            greeted = False
        finally:
            receipt = getattr(boss, 'last_greeting_result', None)
            if isinstance(receipt, dict):
                store.candidate(run_id, cid, greeting_receipt=receipt)
        if greeted is not True:
            reason = store.get(run_id)['candidates'][cid].get('greeting_error') or '连接器未返回成功确认'
            store.candidate(run_id, cid, state='needs_review', greeting_error=reason, greeting_attempted=True)
            store.update(run_id, status='paused', error=f'打招呼结果不明，不会自动重发：{reason}'[:300])
            return False
        store.candidate(run_id, cid, state='greet_verified', greet_verified=True, greeting_attempted=True, greeting_error=None)
    if _stopped(store, run_id):
        return False
    candidate = store.get(run_id)['candidates'][cid]
    outreach = candidate.get('outreach') or {}
    if outreach.get('status') not in {'approved', 'fixed'} or not outreach.get('message'):
        store.candidate(run_id, cid, state='needs_review')
        store.update(run_id, status='paused', error='已打招呼但缺少已审核的消息，请人工核查')
        return False
    store.candidate(run_id, cid, state='message_pending')
    try:
        sent = boss.send_first(cid, outreach['message'])
    except Exception as exc:
        if getattr(exc, 'not_dispatched', False):
            store.candidate(run_id, cid, state='greet_verified', message_error=str(exc)[:240])
            store.update(run_id, status='paused', error=f'首条消息尚未发送：{str(exc)[:240]}')
            return False
        store.candidate(run_id, cid, message_error=f'{type(exc).__name__}: {str(exc)[:240]}')
        sent = False
    if sent is not True:
        store.candidate(run_id, cid, state='needs_review')
        reason = store.get(run_id)['candidates'][cid].get('message_error') or '历史消息尚未确认送达'
        store.update(run_id, status='paused', error=f'首条消息结果不明，不会自动重发：{reason}'[:300])
        return False
    store.candidate(run_id, cid, state='waiting_resume', message_verified=True)
    return True


def _save_shadow(store, run_id, cid, shadow, rubric, text, judgement, scored, stage, coverage, threshold):
    key = 'shadow_coarse' if stage == 'precontact' else 'shadow_fine'
    try:
        result = (shadow.score(rubric, text, judgement, stage, coverage, threshold)
                  if not scored.get('scoring_version') else {'status': 'not_applicable_to_detailed'})
    except Exception as exc:
        result = {'error': type(exc).__name__}
    store.candidate(run_id, cid, **{key: result})


def _fine_after_contact(store, run_id, cid, model, boss, rubric, shadow):
    store.candidate(run_id, cid, state='waiting_resume')
    try:
        fetch = getattr(boss, 'contacted_resume', None) or boss.full_resume
        resume = fetch(cid)
    except Exception as exc:
        if getattr(exc, 'rate_limited', False):
            raise
        store.candidate(run_id, cid, resume_error=f'等待完整简历：{type(exc).__name__}: {str(exc)[:160]}')
        return
    if (resume.get('candidate_id') != cid or resume.get('coverage') != 'complete'
            or not isinstance(resume.get('text'), str) or not resume['text'].strip()):
        store.candidate(run_id, cid, resume_error='已联系，暂未获得可核实的完整简历，请稍后恢复任务')
        return
    if len(resume['text']) > 30000:
        store.candidate(run_id, cid, state='resume_too_long', resume_error='简历超过30000字，未截断评分')
        return
    if _stopped(store, run_id):
        return
    data = store.get(run_id)
    judgement, fine = _assess(model, 'full_resume', rubric, resume['text'], 'complete', data['fine_threshold'])
    store.candidate(run_id, cid, fine=fine, fine_completed=True, resume_error=None,
                    fine_source=resume.get('source', 'unknown'),
                    fine_sha256=hashlib.sha256(resume['text'].encode('utf-8')).hexdigest(),
                    state='sent_verified' if fine['decision'] == 'high_match' else 'fine_done')
    _save_shadow(store, run_id, cid, shadow, rubric, resume['text'], judgement, fine,
                 'full_resume', 'complete', data['fine_threshold'])
    store.export(run_id)


def run_pipeline(store: RunStore, run_id: str, model, boss, shadow=None) -> None:
    data = store.get(run_id)
    if data['status'] not in {'queued', 'paused', 'failed', 'waiting_resume'}:
        raise ValueError('运行状态不允许启动')
    try:
        store.update(run_id, status='running', error=None, end_reason=None, pipeline_version='contact-before-fine-v2')
        shadow = shadow if shadow is not None else ShadowMatcher()
        rubric = data['rubric'] or validate_rubric(data['job'], model.rubric(data['job']))
        store.update(run_id, title=rubric['title'], rubric=rubric)
        processed = set()
        # Resume contacted candidates even when they disappeared from recommendations.
        for cid, candidate in data['candidates'].items():
            if candidate.get('state') in {'greet_pending', 'message_pending'}:
                store.candidate(run_id, cid, state='needs_review', greeting_attempted=True)
            if candidate.get('state') in {'greet_pending', 'message_pending', 'needs_review'}:
                continue
            sent = candidate.get('message_verified') or candidate.get('state') == 'sent_verified'
            if candidate.get('fine_completed') or (candidate.get('state') == 'sent_verified' and candidate.get('fine')):
                continue
            if sent or candidate.get('greet_verified'):
                if _stopped(store, run_id):
                    return
                if not sent and not _contact(store, run_id, cid, model, boss, rubric):
                    if store.get(run_id)['status'] == 'paused':
                        return
                    continue
                _fine_after_contact(store, run_id, cid, model, boss, rubric, shadow)
                processed.add(cid)
                if store.get(run_id)['status'] == 'paused':
                    return
        if _used(store.get(run_id)) < data['quota']:
            if hasattr(boss, 'iter_cards'):
                boss.skip_candidate_ids = {
                    cid for cid, c in store.get(run_id)['candidates'].items()
                    if c.get('greeting_attempted') or c.get('greet_verified') or c.get('fine_completed')
                    or c.get('state') in {'needs_review', 'message_rejected'}
                    or (c.get('state') == 'coarse_done' and c.get('coarse', {}).get('decision') != 'contact')
                }
            get_cards = getattr(boss, 'iter_cards', None) or boss.cards
            found = False
            for card in get_cards():
                found = True
                if _stopped(store, run_id):
                    return
                if _used(store.get(run_id)) >= data['quota']:
                    break
                cid = card['candidate_id']
                existing = store.get(run_id)['candidates'].get(cid, {})
                if cid in processed or existing.get('greeting_attempted') or existing.get('greet_verified') or existing.get('state') in {
                        'needs_review', 'sent_verified', 'fine_done', 'message_rejected'}:
                    continue
                text_hash = hashlib.sha256(card['text'].encode('utf-8')).hexdigest()
                if not existing.get('coarse') or existing.get('coarse_sha256') != text_hash:
                    judgement, coarse = _assess(model, 'precontact', rubric, card['text'], 'partial', data['coarse_threshold'])
                    store.candidate(run_id, cid, name=card['name'], coarse=coarse,
                                    coarse_text=card['text'], coarse_sha256=text_hash,
                                    coarse_source=card.get('source', 'unknown'), captured_at=card.get('captured_at'),
                                    state='coarse_done', outreach=None)
                    _save_shadow(store, run_id, cid, shadow, rubric, card['text'], judgement, coarse,
                                 'precontact', 'partial', data['coarse_threshold'])
                else:
                    coarse = existing['coarse']
                    store.candidate(run_id, cid, coarse_text=card['text'])
                if coarse['decision'] != 'contact':
                    continue
                if not _contact(store, run_id, cid, model, boss, rubric):
                    if store.get(run_id)['status'] == 'paused':
                        return
                    continue
                _fine_after_contact(store, run_id, cid, model, boss, rubric, shadow)
                if store.get(run_id)['status'] == 'paused':
                    return
                if _used(store.get(run_id)) >= data['quota']:
                    break
            if not found and not processed and not store.get(run_id)['candidates']:
                raise RuntimeError('未读取到候选人，任务未执行筛选；请检查推荐列表后重试')
        store.export(run_id)
        if _stopped(store, run_id):
            return
        current = store.get(run_id)
        waiting = any(c.get('state') == 'waiting_resume' for c in current['candidates'].values())
        uncertain = any(c.get('state') == 'needs_review' for c in current['candidates'].values())
        limited = getattr(boss, 'end_reason', None) == 'scan_limit' and _used(current) < data['quota']
        store.update(run_id, status='paused' if uncertain or limited else 'waiting_resume' if waiting else 'finished',
                     end_reason=('needs_review' if uncertain else 'waiting_resume' if waiting else
                                 'quota_reached' if _used(current) >= data['quota'] else
                                 getattr(boss, 'end_reason', None) or 'no_more_candidates'),
                     error='存在发送结果待核查的候选人，不会自动重复联系' if uncertain else None)
    except Exception as exc:
        store.update(run_id, status='paused' if getattr(exc, 'rate_limited', False) or getattr(exc, 'not_dispatched', False) else 'failed', error=str(exc)[:300])
        raise
