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
               scoring_version: str = 'legacy-v3') -> str:
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
                "scoring_version": scoring_version,
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
            data["contacted"] = sum(c.get("state") == "sent_verified" for c in data["candidates"].values())
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
                if candidate.get("state") == "sent_verified":
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


def run_pipeline(store: RunStore, run_id: str, model, boss, shadow=None) -> None:
    data = store.get(run_id)
    if data["status"] not in {"queued", "paused", "failed"}:
        raise ValueError("运行状态不允许启动")
    try:
        store.update(run_id, status="running", error=None)
        shadow = shadow if shadow is not None else ShadowMatcher()
        rubric = data["rubric"] or validate_rubric(data["job"], model.rubric(data["job"]))
        store.update(run_id, title=rubric["title"], rubric=rubric)
        candidates = boss.cards()
        resumes = {}
        for card in candidates:
            if store.get(run_id)["status"] == "stop_requested":
                store.update(run_id, status="paused")
                return
            cid = card["candidate_id"]
            existing = store.get(run_id)["candidates"].get(cid, {})
            if existing.get("state") not in {None, "coarse_done"}:
                continue
            if existing:
                coarse = existing["coarse"]
            else:
                judgement, coarse = _assess(model, "precontact", rubric, card["text"],
                                            "partial", data["coarse_threshold"])
                store.candidate(run_id, cid, name=card["name"], coarse=coarse,
                                coarse_source=card.get("source", "unknown"),
                                captured_at=card.get("captured_at"),
                                coarse_sha256=hashlib.sha256(card["text"].encode("utf-8")).hexdigest(),
                                state="coarse_done")
                try:
                    store.candidate(run_id, cid, shadow_coarse=shadow.score(
                        rubric, card["text"], judgement, "precontact", "partial", data["coarse_threshold"])
                        if not coarse.get("scoring_version") else {"status": "not_applicable_to_detailed"})
                except Exception as exc:  # shadow failure cannot affect contact decisions
                    store.candidate(run_id, cid, shadow_coarse={"error": type(exc).__name__})
            if coarse["decision"] != "contact":
                continue
            resume = boss.full_resume(cid)
            if resume.get("candidate_id") != cid or resume.get("coverage") != "complete" or not resume.get("text"):
                store.candidate(run_id, cid, state="insufficient_resume")
                continue
            if len(resume["text"]) > 30000:
                store.candidate(run_id, cid, state="resume_too_long")
                continue
            judgement, fine = _assess(model, "full_resume", rubric, resume["text"],
                                      "complete", data["fine_threshold"])
            store.candidate(run_id, cid, fine=fine, fine_source=resume.get("source", "unknown"),
                            fine_sha256=hashlib.sha256(resume["text"].encode("utf-8")).hexdigest(),
                            state="qualified" if fine["decision"] == "high_match" else "fine_done")
            if fine['decision'] == 'high_match':
                resumes[cid] = resume
            try:
                store.candidate(run_id, cid, shadow_fine=shadow.score(
                    rubric, resume["text"], judgement, "full_resume", "complete", data["fine_threshold"])
                    if not fine.get("scoring_version") else {"status": "not_applicable_to_detailed"})
            except Exception as exc:  # shadow failure cannot affect contact decisions
                store.candidate(run_id, cid, shadow_fine={"error": type(exc).__name__})
        ranked = sorted(store.get(run_id)["candidates"].items(),
                        key=lambda pair: -(pair[1].get("fine", {}).get("score") or -1))
        for cid, candidate in ranked:
            if store.get(run_id)["status"] == "stop_requested":
                store.update(run_id, status="paused")
                return
            used = sum(bool(c.get("greeting_attempted")) for c in store.get(run_id)["candidates"].values())
            if used >= data["quota"]:
                break
            if candidate["state"] != "qualified":
                continue
            if data.get('message_mode', 'fixed') == 'llm':
                try:
                    resume = resumes.get(cid) or boss.full_resume(cid)
                    if (resume.get('candidate_id') != cid or resume.get('coverage') != 'complete' or
                            not isinstance(resume.get('text'), str) or not resume['text'] or len(resume['text']) > 30000):
                        raise ValueError('恢复消息生成时无法核验完整简历')
                    if hashlib.sha256(resume['text'].encode('utf-8')).hexdigest() != candidate.get('fine_sha256'):
                        store.candidate(run_id, cid, state='coarse_done', outreach=None)
                        store.update(run_id, status='paused', error='简历内容已变化，请恢复任务重新精筛')
                        return
                    outreach = MessageComposer(model).prepare(
                        data['job'], resume['text'], candidate['fine'].get('gaps', []), candidate.get('outreach'),
                        save=lambda value: store.candidate(run_id, cid, outreach=value))
                except Exception as exc:
                    # No BOSS writes have happened; the saved draft can be reviewed on resume.
                    store.candidate(run_id, cid, message_error=f'消息生成/复核异常：{type(exc).__name__}')
                    store.update(run_id, status='paused', error=f'消息生成/复核接口异常（{type(exc).__name__}），请检查API后恢复')
                    return
                store.candidate(run_id, cid, outreach=outreach, message_error=None)
                if outreach['status'] != 'approved':
                    store.candidate(run_id, cid, state='message_rejected')
                    continue
                message = outreach['message']
            else:
                message = data['message'].replace('{职位名称}', rubric['title'])
                store.candidate(run_id, cid, outreach={'mode': 'fixed', 'status': 'fixed', 'message': message,
                                                       'reason': '使用用户设定的固定消息'})
            # Stop may have been requested while the generation/review API was running.
            if store.get(run_id)['status'] == 'stop_requested':
                store.update(run_id, status='paused')
                return
            store.candidate(run_id, cid, state="greet_pending", greeting_attempted=True)
            try:
                greeted = boss.greet(cid)
            except Exception:  # noqa: BLE001 - any post-dispatch failure may mean a greeting happened
                store.candidate(run_id, cid, state="needs_review")
                store.update(run_id, status="paused", error="打招呼结果不明，请人工核查后恢复")
                return
            if greeted is not True:
                store.candidate(run_id, cid, state="needs_review")
                store.update(run_id, status="paused", error="打招呼未核实，请人工核查后恢复")
                return
            store.candidate(run_id, cid, state="greet_verified", greet_verified=True)
            store.candidate(run_id, cid, state="message_pending")
            try:
                sent = boss.send_first(cid, message)
            except Exception:  # noqa: BLE001 - never replay an uncertain message send
                store.candidate(run_id, cid, state="needs_review")
                store.update(run_id, status="paused", error="首条消息结果不明，请人工核查后恢复")
                return
            store.candidate(run_id, cid, state="sent_verified" if sent is True else "needs_review")
            if sent is True:
                store.export(run_id)
            else:
                store.update(run_id, status="paused", error="首条消息未核实，请人工核查后恢复")
                return
        store.export(run_id)
        store.update(run_id, status="finished")
    except Exception as exc:
        store.update(run_id, status="failed", error=str(exc)[:300])
        raise
