import json
import re
import threading
import time

import httpx
import pytest

from recruitment_app.boss import BossBrowser
from recruitment_app.llm import JobModel
from recruitment_app.web import create_server


def test_model_rejects_untrusted_destination():
    with pytest.raises(ValueError, match="DashScope"):
        JobModel("key", "https://example.com/compatible-mode/v1")


def test_model_parses_job_rubric_from_mocked_provider():
    from .test_core import JOB, RUBRIC

    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(RUBRIC, ensure_ascii=False)}}]})

    model = JobModel("test-key", "https://dashscope.aliyuncs.com/compatible-mode/v1",
                     transport=httpx.MockTransport(handler))
    assert model.rubric(JOB)["title"] == "数据工程师"
    assert "岗位" in calls[0]["messages"][0]["content"]


def test_evidence_uses_hosted_llm_with_stage_specific_matching():
    from .test_core import RUBRIC

    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    model = JobModel("test-key", "https://dashscope.aliyuncs.com/compatible-mode/v1",
                     transport=httpx.MockTransport(handler))
    model.evidence("precontact", RUBRIC, "负责数据接入")
    model.evidence("full_resume", RUBRIC, "负责数据接入")
    assert len(calls) == 2
    assert all(call["model"] == "qwen-plus" for call in calls)
    assert all(call["enable_thinking"] is False for call in calls)
    assert "可迁移" in calls[0]["messages"][0]["content"]
    assert "亲自执行" in calls[1]["messages"][0]["content"]


def test_detailed_evidence_resolves_line_spans_without_model_rewriting_quotes():
    from .test_core import RUBRIC
    payload = {"claims": {"sql": {"level": 3, "fit": 4, "start_line": 1, "end_line": 2}},
               "requirements": {}, "reason": "有 SQL 清洗经验。", "gaps": []}
    def handler(request):
        body = json.loads(request.content)
        assert "[1]" in body["messages"][-1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})
    model = JobModel("test-key", "https://dashscope.aliyuncs.com/compatible-mode/v1", transport=httpx.MockTransport(handler))
    source = "使用 SQL 查询数据，\n清洗并核对结果。"
    result = model.detailed_evidence("full_resume", RUBRIC, source)
    assert result["claims"]["sql"]["evidence"] == source
    payload["claims"]["sql"]["end_line"] = 999
    result = model.detailed_evidence("full_resume", RUBRIC, source)
    assert result["claims"]["sql"]["evidence"] == ""


def test_short_card_uses_whole_source_as_evidence_scope():
    result = JobModel._restore_spans({"claims": {"sql": {"level": 2, "fit": 3, "start_line": 5, "end_line": 5}},
                                     "requirements": {}}, "使用 SQL 处理数据")
    assert result["claims"]["sql"]["evidence"] == "使用 SQL 处理数据"
    assert result["claims"]["sql"]["evidence_scope"] == "whole_card"


class StubSession:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []
        self.account_key = "account"

    def navigate(self, page):
        self.calls.append(("navigate", page))

    def call(self, operation, args=None):
        self.calls.append((operation, args))
        if operation == "cards":
            return [{"geek_id": "c1", "name": "甲", "text": "负责数据接入；熟悉 SQL"}]
        if operation == "profile_snapshot":
            return self.snapshot
        if operation == "open_profile":
            return {"opened": True}
        raise AssertionError(operation)


def test_browser_only_accepts_verified_full_resume_for_same_candidate():
    session = StubSession({"full_resume": {"candidate_id": "other", "coverage": "complete",
                                                    "verified": True, "text": "完整简历"}})
    boss = BossBrowser(session)
    assert boss.cards()[0]["candidate_id"] == "c1"
    assert boss.full_resume("c1")["coverage"] == "partial"
    session.snapshot["full_resume"]["candidate_id"] = "c1"
    session.snapshot["full_resume"]["sections_complete"] = True
    assert boss.full_resume("c1")["coverage"] == "complete"


def test_precontact_cards_include_only_identity_matched_readable_abstract():
    session = StubSession({"frames": [{"resumeTap": {"messages": [{"type": "IFRAME_DONE",
        "data": {"abstractData": {"encryptGeekId": "c1", "geekBaseInfo": {"intro": "做过客户实施"}}}}]}}]})
    text = BossBrowser(session).cards()[0]["text"]
    assert "做过客户实施" in text


def test_long_resume_is_not_silently_truncated(tmp_path):
    from recruitment_app.runner import RunStore, run_pipeline

    from .test_core import JOB, FakeBoss, FakeModel

    class LongResume(FakeBoss):
        def full_resume(self, candidate_id):
            return {"candidate_id": candidate_id, "text": "内容" * 20000,
                    "coverage": "complete", "source": "test"}

    store = RunStore(tmp_path)
    boss = LongResume()
    run_id = store.create(JOB, 1, 30, 75, "你好")
    run_pipeline(store, run_id, FakeModel(), boss)
    assert boss.greeted == []
    assert store.get(run_id)["candidates"]["id-1"]["state"] == "resume_too_long"


def test_first_message_requires_matching_session_and_history_confirmation():
    class SendSession:
        def __init__(self):
            self.sent = []

        def rpc(self, path):
            return {"allow_writes": True, "connected": True}

        def navigate(self, page):
            assert page == "chat"

        def call(self, operation, args):
            assert operation == "chat_send"
            self.sent.append(args)
            return {"invoked": True}

    class SendBoss(BossBrowser):
        def _relation(self, candidate_id):
            return {"friendId": 12, "uid": 345, "encryptFriendId": candidate_id, "friendSource": 0}

        def _history(self, friend_id):
            return [{"received": False, "body": {"text": "你好"}}] if self.session.sent else []

    session = SendSession()
    assert SendBoss(session).send_first("candidate_123456", "你好") is True
    assert session.sent == [{"uid": 345, "encrypt_uid": "candidate_123456", "friend_source": 0,
                             "message": "你好"}]


def test_first_message_waits_for_new_session(monkeypatch):
    class Session:
        def __init__(self):
            self.sent = False

        def rpc(self, path):
            return {"allow_writes": True, "connected": True}

        def navigate(self, page):
            pass

        def call(self, operation, args):
            self.sent = True
            return {"invoked": True}

    class DelayedBoss(BossBrowser):
        attempts = 0

        def _relation(self, candidate_id):
            self.attempts += 1
            if self.attempts < 3:
                raise RuntimeError("打招呼后未找到与候选人 ID 对应的会话")
            return {"friendId": 12, "uid": 345, "encryptFriendId": candidate_id, "friendSource": 0}

        def _history(self, friend_id):
            return [{"received": False, "body": {"text": "你好"}}] if self.session.sent else []

    monkeypatch.setattr("recruitment_app.boss.time.sleep", lambda _: None)
    boss = DelayedBoss(Session())
    assert boss.send_first("candidate_123456", "你好") is True
    assert boss.attempts == 3


def test_local_web_bind_and_start_contract(tmp_path):
    server = create_server(tmp_path, host="127.0.0.1", port=0, model_factory=lambda: None, boss_factory=lambda: None)
    try:
        assert server.server_address[0] == "127.0.0.1"
        assert server.server_address[1] > 0
    finally:
        server.server_close()


def test_detailed_prompt_uses_hosted_model_and_requests_reason():
    calls = []

    def transport(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"claims": {}, "requirements": {}, "reason": "证据不足", "gaps": []}, ensure_ascii=False)
        }}]})

    from recruitment_app.llm import JobModel

    model = JobModel("test-key", "https://dashscope.aliyuncs.com/compatible-mode/v1",
                     transport=httpx.MockTransport(transport))
    result = model.detailed_evidence("full_resume", {"criteria": [], "requirements": []}, "数据工程师")
    assert result["reason"] == "证据不足"
    prompt = calls[0]["messages"][0]["content"]
    assert "fit" in prompt and "0至4" in prompt and "理由" in prompt


def test_local_eval_web_endpoint_does_not_create_boss_session(tmp_path):
    from .test_core import JOB, RUBRIC

    class Model:
        model = "fake-qwen"

        def rubric(self, job):
            return RUBRIC

        def detailed_evidence(self, stage, rubric, text):
            return {"claims": {
                "delivery": {"level": 4, "fit": 4, "evidence": "数据接入"},
                "sql": {"level": 4, "fit": 4, "evidence": "SQL"}},
                "requirements": {"degree": {"status": "met", "evidence": "本科"}},
                "reason": "有数据接入和 SQL 证据。", "gaps": []}

    def no_boss():
        raise AssertionError("local evaluation must not connect BOSS")

    cases = lambda root: [{"id": "S-test", "group": "synthetic", "tier": "strong_match",
                           "expected_coarse": "pass", "expected_fine": "pass",
                           "text": "求职意向：数据工程师。负责数据接入和 SQL 查询，本科毕业。"}]
    server = create_server(tmp_path, host="127.0.0.1", port=0,
                           model_factory=Model, boss_factory=no_boss,
                           local_cases_factory=cases)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as client:
            page = client.get("/").text
            assert "评测本地样本" in page
            assert "匹配理由" in page
            token = re.search(r'name="run-token" content="([^"]+)"', page).group(1)
            started = client.post("/api/local-eval", json={"job": JOB}, headers={"X-Run-Token": token})
            assert started.status_code == 201
            eval_id = started.json()["id"]
            for _ in range(100):
                result = client.get(f"/api/local-eval/{eval_id}").json()
                if result["status"] == "finished":
                    break
                time.sleep(.01)
            assert result["status"] == "finished"
            assert result["candidates"][0]["fine"]["reason"]
            assert result["candidates"][0]["show_in_web"] is True
            assert client.get(f"/api/local-eval/{eval_id}/report").json()["rows"][0]["id"] == "S-test"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_page_can_discover_running_task_without_browser_storage(tmp_path):
    from recruitment_app.runner import RunStore

    from .test_core import JOB

    store = RunStore(tmp_path)
    run_id = store.create(JOB, 1, 30, 75, "你好")
    server = create_server(tmp_path, host="127.0.0.1", port=0,
                           model_factory=lambda: None, boss_factory=lambda: None)
    store.update(run_id, status="running")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as client:
            response = client.get("/api/active-run")
            assert response.status_code == 200
            assert response.json()["id"] == run_id
            assert response.json()["status"] == "running"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize('mode', ['fixed', 'llm'])
def test_one_page_starts_job_and_reports_verified_result(tmp_path, mode):
    from .test_core import JOB, FakeBoss, FakeModel
    from .test_messages import MessagingModel, MESSAGE

    server = create_server(tmp_path, host="127.0.0.1", port=0,
                           model_factory=FakeModel if mode == 'fixed' else lambda: MessagingModel([
                               {'message': MESSAGE}, {'approved': True, 'reason': '事实支持'}]), boss_factory=FakeBoss)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as client:
            page = client.get("/")
            assert page.status_code == 200
            token = re.search(r'name="run-token" content="([^"]+)"', page.text).group(1)
            response = client.post("/api/runs", json={"job": JOB, "quota": 1,
                                  "message_mode": mode,
                                  "message": "你好，我们在招「{职位名称}」。" if mode == 'fixed' else ''},
                                   headers={"X-Run-Token": token})
            assert response.status_code == 201
            run_id = response.json()["id"]
            for _ in range(100):
                result = client.get(f"/api/runs/{run_id}").json()
                if result["status"] == "finished":
                    break
                time.sleep(0.01)
            assert result["contacted"] == 1
            assert result["fine_passed"] == 1
            assert result["candidates"][0]["name"] == "测试甲"
            assert "reason" in result["candidates"][0]
            assert result['message_mode'] == mode
            assert result['candidates'][0]['message_status'] == ('fixed' if mode == 'fixed' else 'approved')
            assert result['candidates'][0]['message_text'] == ('你好，我们在招「数据工程师」。' if mode == 'fixed' else MESSAGE)
            assert 'id="run-table"' in page.text
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
