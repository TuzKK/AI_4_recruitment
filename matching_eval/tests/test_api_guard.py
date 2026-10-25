import httpx
import pytest
from matching_eval.api_guard import AccountBlocked, guard_model, API_ABORT


def test_arrearage_stops_subsequent_calls_without_retry():
    API_ABORT.clear()
    calls=[]
    class Model:
        def _ask(self,*args):
            calls.append(1)
            response=httpx.Response(400,json={'error':{'code':'Arrearage','message':'Access denied'}},
                                    request=httpx.Request('POST','https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'))
            response.raise_for_status()
    model=guard_model(Model())
    try:
        for _ in range(2):
            with pytest.raises(AccountBlocked,match='Arrearage'):
                model._ask('system','user')
        assert len(calls)==1
    finally:
        API_ABORT.clear()


def test_ordinary_http_error_remains_retryable():
    API_ABORT.clear()
    class Model:
        def _ask(self,*args):
            response=httpx.Response(429,json={'error':{'code':'Throttling'}},
                                    request=httpx.Request('POST','https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'))
            response.raise_for_status()
    with pytest.raises(httpx.HTTPStatusError):
        guard_model(Model())._ask('system','user')
    assert not API_ABORT.is_set()
