"""Read-only probe for responses loaded when one recommended profile opens.

The output contains candidate data and stays under the ignored .runtime directory.
It is diagnostic evidence, not a claim that the resume is complete.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from boss_cli.browser_session import resolve_browser_session
from boss_cli.precontact_abstract import matching_resume_message, project_readable_resume
from boss_cli.resume_export import render_resume


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geek-id', help='Current recommendation card ID; defaults to the first card')
    parser.add_argument('--index', type=int, default=0, help='Card position after refresh, starting at zero')
    parser.add_argument('--wait', type=int, default=5, choices=range(1, 16))
    args = parser.parse_args()
    if args.index < 0:
        parser.error('--index must be non-negative')
    session = resolve_browser_session()
    if session is None:
        raise RuntimeError('需要已连接的浏览器通道')
    refreshed = session.call('navigate', {'page': 'recommend', 'refresh': True})
    session.target = refreshed['target']
    session.account_key = refreshed['account_key']
    cards = []
    for _ in range(20):
        cards = session.call('cards')
        if cards:
            break
        time.sleep(0.5)
    if not cards:
        raise RuntimeError('推荐页没有可读取卡片')
    matches = [card for card in cards if card['geek_id'] == args.geek_id] if args.geek_id else cards[args.index:args.index + 1]
    if len(matches) != 1:
        raise RuntimeError('指定候选人卡片不存在或重复')
    card = matches[0]
    folder = Path('.runtime/precontact-network') / datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'card.private.json').write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding='utf-8')
    session.call('profile_network', {'action': 'start', 'geek_id': card['geek_id']})
    opened = None
    try:
        opened = session.call('open_profile', {'geek_id': card['geek_id']})
        time.sleep(args.wait)
        snapshot = session.call('profile_snapshot')
        (folder / 'snapshot.private.json').write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        network = session.call('profile_network', {'action': 'stop', 'geek_id': card['geek_id']})
        (folder / 'network.private.json').write_text(
            json.dumps(network, ensure_ascii=False, indent=2), encoding='utf-8')
    message = matching_resume_message(snapshot, card['geek_id'])
    readable = project_readable_resume(message) if message else {}
    if readable:
        (folder / 'abstract.private.json').write_text(
            json.dumps(readable, ensure_ascii=False, indent=2), encoding='utf-8')
        note = ('# 推荐页已可读信息（完整性待核验）\n\n'
                '此文件来自与当前卡片身份匹配的页面完成消息；正文和页面底部仍需核对。\n\n')
        (folder / 'abstract.private.md').write_text(
            note + render_resume(readable, card['geek_id'], str(message.get('jobId') or '')),
            encoding='utf-8')
    summary = {
        'status': 'partial' if readable and not readable.get('geekDetailInfo') else 'unverified',
        'reason': 'abstract_only' if readable and not readable.get('geekDetailInfo') else 'requires_page_review',
        'opened': bool(opened),
        'card_count': len(cards),
        'response_count': len(network['responses']),
        'detached': network['detached'],
        'readable': {'identity_matched': bool(message), 'fields': list(readable),
                     'work_count': len(readable.get('geekWorkExpList') or []),
                     'project_count': len(readable.get('geekProjExpList') or []),
                     'education_count': len(readable.get('geekEduExpList') or []),
                     'detail_present': bool(readable.get('geekDetailInfo'))},
        'responses': [{'path': response['path'], 'status': response['status'],
                       'body_length': len(response.get('body') or ''),
                       'error': response.get('error')}
                      for response in network['responses']],
        'frames': [{'path': (frame.get('url') or '').split('?')[0], 'text_length': len(frame.get('text', '')),
                    'section_lengths': [len(section['text']) for section in frame.get('sections', [])],
                    'resume_tap': ({'parse_count': frame['resumeTap']['parseCount'],
                                    'draw_count': frame['resumeTap']['drawCount'],
                                    'detail_count': len(frame['resumeTap']['details']),
                                    'drawn_text_count': len(frame['resumeTap']['drawnText']),
                                    'messages': [
                                        {'type': message.get('type'),
                                         'abstract_keys': sorted((message.get('data', {}).get('abstractData') or {}).keys()),
                                         'error_message': str(message.get('data', {}).get('message', ''))[:300]}
                                        for message in frame['resumeTap'].get('messages', [])]}
                                   if frame.get('resumeTap') else None)}
                   for frame in snapshot['frames']],
    }
    (folder / 'manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'output={folder}')
    print(f"responses={summary['response_count']} detached={summary['detached']}")
    print(f"status={summary['status']} reason={summary['reason']}")


if __name__ == '__main__':
    main()
