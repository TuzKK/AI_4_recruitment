from boss_cli.precontact_abstract import matching_resume_message, project_readable_resume


def test_matches_only_current_candidate_and_projects_readable_fields():
    snapshot = {'frames': [
        {'resumeTap': {'messages': [
            {'type': 'IFRAME_DONE', 'data': {'abstractData': {'encryptGeekId': 'other'}}},
            {'type': 'IFRAME_DONE', 'data': {'abstractData': {
                'encryptGeekId': 'target', 'geekDetailInfo': None,
                'geekBaseInfo': {'name': 'Example'},
                'geekWorkExpList': [{'company': 'Test Co'}],
                'encryptGeekDetailInfo': 'ciphertext'}}}]}},
    ]}
    message = matching_resume_message(snapshot, 'target')
    assert message['encryptGeekId'] == 'target'
    assert project_readable_resume(message) == {
        'geekBaseInfo': {'name': 'Example'},
        'geekWorkExpList': [{'company': 'Test Co'}],
    }


def test_rejects_missing_or_ambiguous_identity():
    message = {'type': 'IFRAME_DONE', 'data': {'abstractData': {'encryptGeekId': 'target'}}}
    snapshot = {'frames': [{'resumeTap': {'messages': [message, message]}}]}
    assert matching_resume_message(snapshot, 'target') is None
    assert matching_resume_message(snapshot, 'other') is None
