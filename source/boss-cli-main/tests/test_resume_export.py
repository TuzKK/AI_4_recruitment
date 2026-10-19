import json

from click.testing import CliRunner

from boss_cli.cli import cli


def test_export_keeps_unknown_fields_long_text_and_candidate_identity(monkeypatch):
    from boss_cli.commands import recruiter
    tail = '经验' * 4000 + '末尾成果必须保留'
    monkeypatch.setattr(recruiter, 'require_auth', lambda: object())
    monkeypatch.setattr(recruiter, 'run_client_action', lambda *_: {
        'geekDetailInfo': {'geekBaseInfo': {'name': '同名', 'degree': 4},
                           'geekWorkExpList': [{'description': tail}],
                           'customAwards': [{'title': '新字段奖项'}]}})
    result = CliRunner().invoke(cli, ['recruiter','resume-download','geek-123','--job','job-456','-o','-'])
    assert result.exit_code == 0, result.output
    assert '末尾成果必须保留' in result.output
    assert '新字段奖项' in result.output
    assert 'geek-123' in result.output and 'job-456' in result.output


def test_chat_exposes_history_cursor(monkeypatch):
    from boss_cli.commands import _common, recruiter
    seen = {}
    class Client:
        def get_boss_chat_history(self, **kwargs):
            seen.update(kwargs)
            return {'messages': []}
    monkeypatch.setattr(recruiter, 'require_auth', lambda: object())
    monkeypatch.setattr(_common, 'run_client_action', lambda cred, action: action(Client()))
    result = CliRunner().invoke(cli, ['recruiter','chat','123','--before','456','--json'])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['ok']
    assert seen['max_msg_id'] == 456
