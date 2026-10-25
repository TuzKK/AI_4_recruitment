import pytest
from recruitment_app.web import create_server
from recruitment_app.runner import RunStore
from .test_core import JOB


def test_failed_duplicate_start_cannot_recover_running_tasks(tmp_path):
    server = create_server(tmp_path, port=0)
    try:
        store = RunStore(tmp_path)
        run = store.create(JOB, 1, 30, 75, '你好')
        store.update(run, status='running')
        with pytest.raises(OSError):
            duplicate = create_server(tmp_path, port=server.server_port)
            duplicate.server_close()
        assert store.get(run)['status'] == 'running'
    finally:
        server.server_close()
