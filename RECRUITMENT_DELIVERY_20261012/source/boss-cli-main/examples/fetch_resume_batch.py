import json
import time
from pathlib import Path
from boss_cli.browser_session import resolve_browser_session
from boss_cli.client import BossClient

root = Path(__file__).parent
targets = json.loads((root / 'inbox.private.json').read_text(encoding='utf-8'))['friendList'][1:6]
dest = root / 'clean-resumes-20260929'
dest.mkdir(exist_ok=True)
session = resolve_browser_session()
with BossClient(session) as client:
    for i, target in enumerate(targets, 1):
        try:
            data = client.get_boss_view_geek(target['encryptUid'], target['encryptJobId'], target['securityId'])
            (dest / f'{i:02d}.raw.private.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            detail = data.get('geekDetailInfo', {})
            print(json.dumps({'index': i, 'name': detail.get('geekBaseInfo', {}).get('name'), 'hiddenResume': data.get('hiddenResume'), 'work': len(detail.get('geekWorkExpList', [])), 'projects': len(detail.get('geekProjExpList', []))}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({'index': i, 'error': str(exc)}, ensure_ascii=False), flush=True)
        time.sleep(1)
