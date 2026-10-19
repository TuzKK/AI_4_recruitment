import json

import pytest

from matching_eval.model import build_model_request, build_prompt, call_model


def test_resume_prompt_uses_full_text_without_first_stage_anchor():
    job = "本科；SQL；Python；客户交付"
    resume = "项目证据" * 4000
    messages = build_prompt("full_resume", job, resume)
    assert resume in messages[1]["content"]
    assert "粗筛分" not in messages[1]["content"]
    assert "只能引用候选人原文" in messages[0]["content"]


def test_precontact_prompt_identifies_partial_information():
    messages = build_prompt("precontact", "岗位", "目前只看到 SQL")
    assert "联系前" in messages[0]["content"]
    assert "缺失" in messages[0]["content"]


def test_model_request_uses_existing_adapter_and_strict_schema():
    url, headers, body, protocol = build_model_request(
        "full_resume",
        "岗位",
        "工作经历",
        "test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    assert url.endswith("/chat/completions")
    assert headers["Authorization"] == "Bearer test-key"
    assert protocol == "openai_compatible"
    assert body["model"] == "qwen3.8-max-0902"
    assert body["reasoning_effort"] == "xhigh"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True


@pytest.mark.parametrize(
    "base_url",
    [
        "http://dashscope.aliyuncs.com/compatible-mode/v1",
        "https://example.com/compatible-mode/v1",
        "https://dashscope.aliyuncs.com.evil.test/compatible-mode/v1",
    ],
)
def test_model_request_rejects_untrusted_destinations(base_url):
    with pytest.raises(ValueError, match="trusted HTTPS"):
        build_model_request("precontact", "岗位", "SQL", "test-key", base_url=base_url)


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {
                                "education": {"status": "unknown", "evidence": ""},
                                "travel": {"status": "unknown", "evidence": ""},
                                "criteria": {},
                            }
                        )
                    },
                }
            ]
        }


class FakeSession:
    def post(self, url, *, headers, json, timeout):
        return FakeResponse()


def test_model_response_is_parsed_without_network():
    result = call_model(
        "precontact",
        "岗位",
        "SQL",
        "test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        session=FakeSession(),
    )
    assert result["education"]["status"] == "unknown"


def test_model_failure_does_not_turn_into_candidate_rejection():
    class FailedSession:
        def post(self, url, *, headers, json, timeout):
            raise TimeoutError("network unavailable")

    with pytest.raises(RuntimeError, match="model request failed"):
        call_model(
            "precontact",
            "岗位",
            "SQL",
            "test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            session=FailedSession(),
        )
