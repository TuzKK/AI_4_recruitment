"""Extract only candidate-matched, readable resume data from the page's own message."""


READABLE_FIELDS = ('geekDetailInfo', 'geekBaseInfo', 'geekWorkExpList',
                   'geekProjExpList', 'geekEduExpList', 'geekQuestInfo', 'geekQuestInfoV2')


def matching_resume_message(snapshot: dict, geek_id: str) -> dict | None:
    matches = []
    for frame in snapshot.get('frames', []):
        for message in (frame.get('resumeTap') or {}).get('messages', []):
            if message.get('type') != 'IFRAME_DONE':
                continue
            data = (message.get('data') or {}).get('abstractData')
            if isinstance(data, dict) and str(data.get('encryptGeekId')) == str(geek_id):
                matches.append(data)
    return matches[0] if len(matches) == 1 else None


def project_readable_resume(message: dict) -> dict:
    return {key: message[key] for key in READABLE_FIELDS if message.get(key) is not None}
