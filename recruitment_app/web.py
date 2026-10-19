"""Loopback-only one-page controller. No recruitment data is served as HTML."""

from __future__ import annotations

import json
import secrets
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .boss import BossBrowser
from .llm import JobModel
from .generic_model import GenericJobModel
from .local_eval import evaluate_local_cases, load_local_cases
from .runner import RunStore, run_pipeline

ROOT = Path(__file__).resolve().parent


def create_server(root: Path | None = None, *, host: str = "127.0.0.1", port: int = 8765,
                  model_factory=None, boss_factory=None, local_cases_factory=None):
    if host != "127.0.0.1":
        raise ValueError("本地页面只允许绑定 127.0.0.1")
    store = RunStore(root or ROOT / ".runtime")
    store.recover()
    token = secrets.token_urlsafe(24)
    custom_model_factory = model_factory
    model_factory = model_factory or JobModel.from_environment
    boss_factory = boss_factory or BossBrowser.connected
    local_cases_factory = local_cases_factory or load_local_cases
    active = set()
    active_lock = threading.Lock()
    local_eval_jobs = {}
    local_eval_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def _send(self, code, data, content_type="application/json; charset=utf-8"):
            raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _same_origin(self):
            host_header = self.headers.get("Host", "")
            origin = self.headers.get("Origin", "")
            expected = f"http://127.0.0.1:{self.server.server_port}"
            return host_header == f"127.0.0.1:{self.server.server_port}" and (not origin or origin == expected)

        def _state(self, run_id):
            data = store.get(run_id)
            # Only message previews and screening summaries are exposed, not raw resumes.
            return {"id": data["id"], "status": data["status"], "title": data["title"],
                    "contacted": data["contacted"], "quota": data["quota"], "error": data["error"],
                    "message_mode": data.get('message_mode', 'fixed'),
                    "scoring_version": data.get('scoring_version', 'legacy-v3'),
                    "scanned": len(data["candidates"]),
                    "fine_passed": sum(c.get("fine", {}).get("decision") == "high_match" for c in data["candidates"].values()),
                    "insufficient": sum(c.get("state") == "insufficient_resume" for c in data["candidates"].values()),
                    "needs_review": sum(c.get("state") == "needs_review" for c in data["candidates"].values()),
                    "candidates": [{"id": cid, "name": c.get("name", cid),
                                    "coarse_score": c.get("coarse", {}).get("score"),
                                    "fine_score": c.get("fine", {}).get("score"),
                                    "coarse_coverage": c.get('coarse', {}).get('evidence_coverage'),
                                    "fine_coverage": c.get('fine', {}).get('evidence_coverage'),
                                    "decision": c.get("fine", c.get("coarse", {})).get("decision"),
                                    "reason": c.get("fine", c.get("coarse", {})).get("reason", "旧记录未提供理由"),
                                    "gaps": c.get("fine", c.get("coarse", {})).get("gaps", []),
                                    "rule_adjustments": c.get("fine", c.get("coarse", {})).get("rule_adjustments", []),
                                    "contact_state": c.get('state'),
                                    "message_text": (c.get('outreach') or {}).get('message', ''),
                                    "message_status": (c.get('outreach') or {}).get('status', 'pending'),
                                    "message_reason": c.get('message_error') or (c.get('outreach') or {}).get('reason', '')}
                                   for cid, c in data["candidates"].items()]}

        def _launch(self, run_id):
            with active_lock:
                if active:
                    raise ValueError("已有招聘任务在运行")
                active.add(run_id)

            def worker():
                try:
                    factory = model_factory
                    if not custom_model_factory and store.get(run_id).get('scoring_version') == 'generic-v1':
                        factory = GenericJobModel.from_environment
                    run_pipeline(store, run_id, factory(), boss_factory())
                except Exception as exc:  # noqa: BLE001 - background boundary must persist failures
                    if store.get(run_id)["status"] != "failed":
                        store.update(run_id, status="failed", error=str(exc)[:300])
                finally:
                    with active_lock:
                        active.discard(run_id)

            threading.Thread(target=worker, daemon=True).start()

        def do_GET(self):
            if not self._same_origin():
                return self._send(403, {"error": "来源无效"})
            path = urlsplit(self.path).path
            if path == "/":
                html = (ROOT / "index.html").read_text(encoding="utf-8").replace("__CSRF__", token)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if path == "/app.js":
                return self._send(200, (ROOT / "app.js").read_bytes(), "text/javascript; charset=utf-8")
            if path == "/api/sample-job":
                return self._send(200, {"job": (ROOT.parent / "Samples_for_optimization" /
                                                 "recruitment_request.txt").read_text(encoding="utf-8"),
                                         "recommended_thresholds": {"coarse": 2, "fine": 75}})
            if path.startswith("/api/local-eval/"):
                parts = path.strip("/").split("/")
                if len(parts) not in (3, 4):
                    return self._send(404, {"error": "评测任务不存在"})
                eval_id = parts[2]
                try:
                    uuid.UUID(eval_id)
                except ValueError:
                    return self._send(404, {"error": "评测任务不存在"})
                with local_eval_lock:
                    state = dict(local_eval_jobs.get(eval_id, {}))
                if not state:
                    return self._send(404, {"error": "评测任务不存在"})
                if len(parts) == 4 and parts[3] == "report":
                    report_path = store.root / "local_evals" / f"{eval_id}.json"
                    if not report_path.exists():
                        return self._send(404, {"error": "完整报告尚未生成"})
                    return self._send(200, json.loads(report_path.read_text(encoding="utf-8")))
                if len(parts) == 4:
                    return self._send(404, {"error": "接口不存在"})
                report_path = store.root / "local_evals" / f"{eval_id}.json"
                if state["status"] == "finished" and report_path.exists():
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    state["candidates"] = [row for row in report["rows"] if row["show_in_web"]]
                    state["summary"] = {key: report[key] for key in ("tiers", "coarse_metrics", "fine_metrics", "pipeline_metrics",
                                                                      "suggested_coarse", "suggested_fine", "topk")}
                return self._send(200, state)
            if path == "/api/active-run":
                with active_lock:
                    active_ids = set(active)
                files = sorted((store.root / "runs").glob("*.json"),
                               key=lambda item: item.stat().st_mtime, reverse=True)
                for file in files:
                    run_id = file.stem
                    if run_id in active_ids or store.get(run_id)["status"] in {"running", "stop_requested"}:
                        return self._send(200, self._state(run_id))
                if files:
                    return self._send(200, self._state(files[0].stem))
                return self._send(200, {"id": None})
            if path.startswith("/api/runs/"):
                try:
                    return self._send(200, self._state(path.removeprefix("/api/runs/")))
                except (FileNotFoundError, ValueError):
                    return self._send(404, {"error": "任务不存在"})
            return self._send(404, {"error": "页面不存在"})

        def do_POST(self):
            if not self._same_origin() or self.headers.get("X-Run-Token") != token:
                return self._send(403, {"error": "请求来源无效"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100_000:
                    raise ValueError("请求大小无效")
                payload = json.loads(self.rfile.read(length))
                path = urlsplit(self.path).path
                if path == "/api/local-eval":
                    job = payload.get("job", "")
                    if not isinstance(job, str) or len(job.strip()) < 20:
                        raise ValueError("请输入完整招聘需求")
                    coarse_threshold = payload.get("coarse_threshold", 30)
                    fine_threshold = payload.get("fine_threshold", 75)
                    if any(type(x) is not int or not 0 <= x <= 100 for x in (coarse_threshold, fine_threshold)):
                        raise ValueError("评测阈值须为 0 到 100 的整数")
                    with local_eval_lock:
                        if any(s["status"] in {"queued", "running"} for s in local_eval_jobs.values()):
                            raise ValueError("已有本地评测在运行")
                        eval_id = str(uuid.uuid4())
                        local_eval_jobs[eval_id] = {"id": eval_id, "status": "queued", "done": 0,
                                                    "total": 0, "error": None}

                    def local_worker():
                        try:
                            model = model_factory()
                            cases = local_cases_factory(ROOT.parent / "Samples_for_optimization")
                            with local_eval_lock:
                                local_eval_jobs[eval_id].update(status="running", total=len(cases))

                            def progress(done, total, _candidate_id):
                                with local_eval_lock:
                                    local_eval_jobs[eval_id].update(done=done, total=total)

                            report = evaluate_local_cases(job, cases, model,
                                                          store.root / "local_evals" / "cache",
                                                          coarse_threshold=coarse_threshold,
                                                          fine_threshold=fine_threshold,
                                                          on_progress=progress)
                            report_path = store.root / "local_evals" / f"{eval_id}.json"
                            report_path.parent.mkdir(parents=True, exist_ok=True)
                            temporary = report_path.with_suffix(".tmp")
                            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                            temporary.replace(report_path)
                            with local_eval_lock:
                                local_eval_jobs[eval_id]["status"] = "finished"
                        except Exception as exc:  # keep errors visible to local user
                            with local_eval_lock:
                                local_eval_jobs[eval_id].update(status="failed", error=str(exc)[:300])

                    threading.Thread(target=local_worker, daemon=True).start()
                    return self._send(201, {"id": eval_id})
                if path == "/api/runs":
                    with active_lock:
                        if active:
                            raise ValueError("已有招聘任务在运行")
                    default_coarse = 50 if payload.get('scoring_version') == 'generic-v1' else 30
                    run_id = store.create(payload["job"], payload["quota"], payload.get("coarse_threshold", default_coarse),
                                          payload.get("fine_threshold", 75), payload.get("message", ''),
                                          payload.get('message_mode', 'fixed'), payload.get('scoring_version', 'legacy-v3'))
                    self._launch(run_id)
                    return self._send(201, {"id": run_id})
                if path.startswith("/api/runs/") and path.endswith("/stop"):
                    run_id = path.split("/")[3]
                    if store.get(run_id)["status"] != "running":
                        raise ValueError("任务并未运行")
                    store.update(run_id, status="stop_requested")
                    return self._send(200, {"id": run_id, "status": "stop_requested"})
                if path.startswith("/api/runs/") and path.endswith("/resume"):
                    run_id = path.split("/")[3]
                    self._launch(run_id)
                    return self._send(200, {"id": run_id})
                return self._send(404, {"error": "接口不存在"})
            except (KeyError, ValueError, TypeError, FileNotFoundError) as exc:
                return self._send(400, {"error": str(exc)[:200]})

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main():
    server = create_server()
    print(f"打开 http://127.0.0.1:{server.server_port}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
