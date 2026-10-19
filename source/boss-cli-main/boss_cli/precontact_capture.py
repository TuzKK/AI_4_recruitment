"""Experimental, read-only recommended-resume screenshot probe."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path


def next_scroll(top, height, total):
    return min(max(0, total - height), top + max(1, int(height * .8)))


def capture_status(*, bottom, stable, limited):
    return "captured_unverified" if bottom and stable >= 3 and not limited else "partial"


def evidence_key(candidate_id):
    return hashlib.sha256(candidate_id.encode()).hexdigest()[:20]


def save_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


CARDS = """() => Array.from(document.querySelectorAll('[data-geekid]'))
.filter(e => e.getClientRects().length && (e.innerText||'').length >= 30)
.map(e => ({id:e.getAttribute('data-geekid'), name:e.querySelector('[class*=name]')?.textContent?.trim()||'',
text:e.innerText, contact_status:/继续沟通|已沟通/.test(e.innerText)?'contacted':'unknown'}))"""
OPEN = """id => {
const cards=Array.from(document.querySelectorAll('[data-geekid]')).filter(e=>e.getAttribute('data-geekid')===id && e.getClientRects().length);
if(cards.length!==1) throw Error('candidate_missing_or_duplicate');
const candidates=Array.from(cards[0].querySelectorAll('[class*=name],[class*=info],[class*=content]'));
const opener=candidates.find(e=>e.getClientRects().length && (e.innerText||'').trim() && !e.closest('button,a') && !/立即沟通|继续沟通|打招呼|聊天|联系|收藏|点赞|分享/.test(e.innerText||''));
if(!opener) throw Error('safe_detail_opener_missing');
opener.click();
}"""
GUARD = """() => {
const visible=s=>Array.from(document.querySelectorAll(s)).some(e=>e.getClientRects().length);
return {login:visible('.login-dialog,.login-register-box,.sign-form,.login-content'),
verify:visible('.geetest_panel,.nc-container,.captcha-container,.verify-dialog'),
account:document.querySelector('.nav-figure .label-name,.user-name,.user-info .name')?.textContent?.trim()||''};
}"""
# Operate on the actual scroll container, not the surrounding recommendation list.
SCROLLER = """root => {
const nodes=[root,...root.querySelectorAll('*')].filter(e=>e.clientHeight>80 && e.scrollHeight>e.clientHeight+2 && /auto|scroll/.test(getComputedStyle(e).overflowY));
const e=nodes.sort((a,b)=>(b.scrollHeight-b.clientHeight)-(a.scrollHeight-a.clientHeight))[0]||root;
e.setAttribute('data-precontact-scroll','true');
return {top:e.scrollTop,height:e.clientHeight,total:e.scrollHeight};
}"""
MEASURE = """e => ({top:e.scrollTop,height:e.clientHeight,total:e.scrollHeight})"""


def guard(page, account):
    state = page.evaluate(GUARD)
    if state['verify']:
        raise RuntimeError('verification_required')
    if state['login'] or '/login' in page.url:
        raise RuntimeError('login_required')
    if account and state['account'] != account:
        raise RuntimeError('account_changed')


def find_resume(page):
    # Frame objects include cross-origin frames through the browser automation API.
    for frame in page.frames:
        if 'c-resume' in frame.url:
            body = frame.locator('body')
            if body.count() and body.is_visible() and body.evaluate('(e)=>e.scrollHeight>80 && (e.innerText.trim().length>20 || e.querySelector("canvas,img"))'):
                return frame, body
    selectors = '.boss-dialog__body,.dialog-wrap.active,.geek-detail,.resume-dialog'
    for selector in selectors.split(','):
        loc = page.locator(selector).filter(visible=True)
        if loc.count() == 1 and not loc.locator('iframe').count():
            return page.main_frame, loc
    raise RuntimeError('resume_region_missing_or_ambiguous')


def stitch(folder, shots):
    """Only join geometry-confirmed scroll frames; keep all originals."""
    from PIL import Image
    if not shots or any(s.get('unstable') for s in shots):
        return None
    first = shots[0]
    # Only the screenshot of the actual scroll viewport can be stitched by offsets.
    if any(s['height'] != first['height'] or s['total'] != first['total'] for s in shots):
        return None
    images = [Image.open(folder / s['file']).convert('RGB') for s in shots]
    try:
        if any(im.size != images[0].size for im in images):
            return None
        scale = images[0].height / first['height']
        total_pixels = round(first['total'] * scale)
        if total_pixels * images[0].width > 100_000_000:
            return None
        output = Image.new('RGB', (images[0].width, total_pixels))
        output.paste(images[0], (0, 0))
        for previous, current, image in zip(shots, shots[1:], images[1:]):
            delta = current['top'] - previous['top']
            overlap = image.height - round(delta * scale)
            if delta <= 0 or overlap < 1:
                return None
            # Compare overlapping pixels to reject sticky headers or changed rendering.
            from PIL import ImageChops, ImageStat
            prev_image = images[shots.index(previous)]
            difference = ImageChops.difference(prev_image.crop((0, image.height-overlap, image.width, image.height)),
                                               image.crop((0, 0, image.width, overlap)))
            if max(ImageStat.Stat(difference).mean) > 5:
                return None
            output.paste(image.crop((0, overlap, image.width, image.height)),
                         (0, round(current['top'] * scale) + overlap))
        output.save(folder / 'resume-long.png')
        return 'resume-long.png'
    finally:
        for image in images:
            image.close()


def capture(page, card, folder, max_seconds=120, max_segments=100):
    folder.mkdir()
    result = {'candidate': card, 'status': 'partial', 'shots': [], 'reason': 'not_started', 'manual_review': 'pending'}
    start = time.monotonic()
    account = page.evaluate(GUARD)['account']
    try:
        guard(page, account)
        page.evaluate(OPEN, card['id'])
        deadline = start + max_seconds
        frame = region = None
        while time.monotonic() < min(deadline, start + 20):
            guard(page, account)
            try:
                frame, region = find_resume(page)
                break
            except RuntimeError:
                page.wait_for_timeout(250)
        if region is None:
            raise RuntimeError('resume_region_timeout')
        # Expand only ordinary text controls, never contact/share actions.
        for _ in range(10):
            expansion = region.get_by_text('查看全部', exact=True).or_(region.get_by_text('展开', exact=True)).filter(visible=True)
            if not expansion.count():
                break
            expansion.first.click(timeout=2000)
            page.wait_for_timeout(300)
        region.evaluate(SCROLLER)
        scroll = frame.locator('[data-precontact-scroll=true]')
        if scroll.count() != 1:
            raise RuntimeError('scroll_container_ambiguous')
        scroll.evaluate('(e)=>e.scrollTop=0')
        result['region'] = {'frame_path': frame.url.split('?')[0], 'canvas_count': region.locator('canvas').count()}
        (folder / 'detail-text.private.txt').write_text(region.inner_text(), encoding='utf-8')
        stable = 0
        last_total = None
        while time.monotonic() < deadline and len(result['shots']) < max_segments:
            guard(page, account)
            page.wait_for_timeout(500)
            metrics = scroll.evaluate(MEASURE)
            if metrics['height'] <= 0:
                raise RuntimeError('empty_scroll_viewport')
            bottom = metrics['top'] + metrics['height'] >= metrics['total'] - 2
            stable = stable + 1 if bottom and last_total == metrics['total'] else 0
            last_total = metrics['total']
            if not result['shots'] or metrics['top'] != result['shots'][-1]['top'] or metrics['total'] != result['shots'][-1]['total']:
                box = scroll.bounding_box()
                if not box:
                    raise RuntimeError('resume_region_not_visible')
                # Browser viewport clip includes Canvas pixels, independent of DOM text.
                view = page.viewport_size
                if box['x'] < 0 or box['y'] < 0 or box['x']+box['width'] > view['width']+1 or box['y']+box['height'] > view['height']+1:
                    raise RuntimeError('resume_region_outside_viewport')
                filename = f"segment-{len(result['shots']):03d}.png"
                image = page.screenshot(path=str(folder / filename), clip=box)
                after = scroll.evaluate(MEASURE)
                result['shots'].append(dict(metrics, file=filename, sha256=hashlib.sha256(image).hexdigest(),
                                           unstable=after != metrics, box=box))
                save_json(folder / 'manifest.json', result)
            if time.monotonic() >= deadline:
                result['reason'] = 'time_or_segment_limit'
                break
            if bottom and stable >= 3:
                result.update(status=capture_status(bottom=True, stable=stable, limited=False), reason='bottom_stable')
                break
            target = next_scroll(metrics['top'], metrics['height'], metrics['total'])
            scroll.evaluate('(e,top)=>e.scrollTop=top', target)
        else:
            result['reason'] = 'time_or_segment_limit'
        if any(s['unstable'] for s in result['shots']):
            result.update(status='partial', reason='layout_changed_during_capture')
        if result['status'] == 'captured_unverified':
            result['stitched'] = stitch(folder, result['shots'])
        result['elapsed_seconds'] = round(time.monotonic()-start, 2)
    except Exception as exc:  # noqa: BLE001 - persist terminal probe failure without sensitive payloads
        # No exception messages containing URLs, authentication headers or response bodies.
        result['status'] = 'partial'
        result['reason'] = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        try:
            page.screenshot(path=str(folder / 'failure.png'))
        except Exception as exc:  # noqa: BLE001
            result['failure_screenshot_error'] = type(exc).__name__
    finally:
        save_json(folder / 'manifest.json', result)
    return result


def independent_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--login', action='store_true')
    parser.add_argument('--candidate-id', action='append', default=[])
    parser.add_argument('--limit', type=int, default=1)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--headed', action='store_true')
    mode.add_argument('--headless', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--profile-dir', type=Path)
    parser.add_argument('--max-seconds', type=int, default=120)
    parser.add_argument('--max-segments', type=int, default=100)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 5 or args.max_seconds < 1 or not 1 <= args.max_segments <= 100:
        parser.error('limit must be 1..5; timeout positive; segments 1..100')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.error('Install the capture extra: uv pip install --python .venv/Scripts/python.exe -e ".[capture]"')
    root = Path(__file__).resolve().parents[1]
    profile = args.profile_dir or root / '.runtime' / 'precontact-browser-profile'
    output = args.output or root / '.runtime' / 'precontact-capture' / datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=False)
    summary = {'mode': 'headed' if args.headed or args.login else 'headless', 'results': [], 'status': 'started'}
    save_json(output / 'manifest.json', summary)
    try:
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(str(profile), channel='chrome',
                headless=not (args.headed or args.login), viewport={'width': 1440, 'height': 1000}, locale='zh-CN')
            try:
                def readonly(route):
                    from urllib.parse import urlsplit
                    path = urlsplit(route.request.url).path.lower()
                    if any(s in path for s in ('/chat/start', '/sendreplymsg', '/sendmsg', '/sendmessage', '/greet')):
                        route.abort()
                    else:
                        route.continue_()
                context.route('**/wapi/**', readonly)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto('https://www.zhipin.com/web/chat/recommend', wait_until='domcontentloaded')
                if args.login:
                    print('Complete login in the independent browser. Waiting up to 180 seconds.', flush=True)
                    deadline = time.monotonic()+180
                    while time.monotonic()<deadline:
                        if page.evaluate(CARDS):
                            summary['status']='login_ready'
                            break
                        page.wait_for_timeout(1000)
                    else:
                        summary['status']='login_timeout'
                else:
                    page.wait_for_timeout(3000)
                    guard(page, '')
                    cards = page.evaluate(CARDS)
                    unique = {c['id']: c for c in cards}
                    selected = [unique[i] for i in args.candidate_id if i in unique] if args.candidate_id else list(unique.values())[:args.limit]
                    if args.candidate_id and any(i not in unique for i in args.candidate_id):
                        raise RuntimeError('requested_candidate_not_on_current_recommendations')
                    if not selected:
                        raise RuntimeError('recommendation_cards_missing')
                    for card in selected[:args.limit]:
                        # Reload between candidates rather than removing application dialogs by JS.
                        if summary['results']:
                            page.goto('https://www.zhipin.com/web/chat/recommend', wait_until='domcontentloaded')
                            page.wait_for_timeout(3000)
                        result = capture(page, card, output / evidence_key(card['id']), args.max_seconds, args.max_segments)
                        summary['results'].append(result)
                        save_json(output / 'manifest.json', summary)
                        if result['reason'] in ('login_required', 'verification_required', 'account_changed'):
                            break
                    summary['status']='captured_unverified' if all(r['status']=='captured_unverified' for r in summary['results']) else 'partial'
            finally:
                context.close()
    except Exception as exc:  # noqa: BLE001 - persist terminal probe failure without sensitive payloads
        summary.update(status='failed', reason=str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__)
    finally:
        save_json(output / 'manifest.json', summary)
        rows = ['# Screenshot verification', '', 'Automatic capture is not a completeness verdict. Manual verification: pending.', '',
                '| Candidate ID | Contact status | Capture status | End reason | Segments |', '|---|---|---|---|---|']
        for r in summary['results']:
            rows.append(f"| {r['candidate']['id']} | {r['candidate']['contact_status']} | {r['status']} | {r['reason']} | {len(r['shots'])} |")
        rows += ['', 'Check candidate identity, expanded sections, overlap continuity, final bottom content, and headed/headless differences.',
                 'Contact status unknown cannot establish pre-contact eligibility. No OCR or scoring was executed.',
                 f"Run status: {summary['status']}; reason: {summary.get('reason', '')}"]
        (output / 'verification.md').write_text('\n'.join(rows), encoding='utf-8')
        print(json.dumps({'status':summary['status'],'output':str(output)}, ensure_ascii=False), flush=True)
    return 0 if summary['status'] in ('captured_unverified', 'login_ready') else 2


def capture_extension(session, card, folder, max_seconds=120, max_segments=100, *, refresh=True):
    import base64

    from .exceptions import BossApiError
    folder.mkdir()
    result = {'candidate': card, 'status': 'partial', 'shots': [], 'reason': 'not_started', 'manual_review': 'pending'}
    start = time.monotonic()
    capture_id = None
    args = {'geek_id': card['id']}
    try:
        if refresh:
            refreshed = session.call('navigate', {'page': 'recommend', 'refresh': True})
            session.target = refreshed['target']
            session.account_key = refreshed['account_key']
        session.call('open_profile', {'geek_id': card['id']})
        time.sleep(2)
        deadline = start + max_seconds
        while time.monotonic() < min(deadline, start + 20):
            try:
                prepared = session.call('profile_capture', dict(args, action='prepare'))
                break
            except BossApiError as exc:
                if '尚未就绪' not in str(exc):
                    raise
                time.sleep(.5)
        else:
            raise RuntimeError('resume_region_timeout')
        capture_id = prepared['capture_id']
        result['region'] = {k: v for k, v in prepared.items() if k not in ('text', 'capture_id')}
        (folder / 'detail-text.private.txt').write_text(prepared.get('text', ''), encoding='utf-8')
        top = 0
        stable = 0
        last_total = None
        needs_warmup = bool(prepared.get('contains_iframe'))
        fit_attempts = 0
        unstable_attempts = 0
        missing_top_attempts = 0
        result['diagnostics'] = []

        def keep_diagnostic(shot, kind):
            image = base64.b64decode(shot.pop('png'), validate=True)
            name = f"diagnostic-{len(result['diagnostics']):03d}.png"
            (folder / name).write_bytes(image)
            result['diagnostics'].append(dict(shot, file=name, kind=kind, sha256=hashlib.sha256(image).hexdigest()))
            save_json(folder / 'manifest.json', result)

        while time.monotonic() < deadline and len(result['shots']) < max_segments:
            shot = session.call('profile_capture', dict(args, action='step', capture_id=capture_id, top=top))
            if shot['height'] <= 0:
                raise RuntimeError('empty_scroll_viewport')
            if needs_warmup:
                # A first browser render can initialize the Canvas and its real host scroller.
                keep_diagnostic(shot, 'render_warmup')
                session.call('profile_capture', dict(args, action='release', capture_id=capture_id))
                capture_id = None
                prepared = session.call('profile_capture', dict(args, action='prepare'))
                capture_id = prepared['capture_id']
                result['region'] = {k: v for k, v in prepared.items() if k not in ('text', 'capture_id')}
                needs_warmup = False
                continue
            if shot.get('cropped'):
                can_fit = shot.get('can_fit_viewport') and fit_attempts == 0
                keep_diagnostic(shot, 'cropped_viewport')
                if can_fit:
                    result['viewport_fit'] = session.call('profile_capture', dict(args, action='fit', capture_id=capture_id))
                    fit_attempts += 1
                    top, stable, last_total = 0, 0, None
                    continue
                result.update(status='partial', reason='visible_viewport_diagnostic_only')
                break
            if shot.get('nested_scroll_uncovered'):
                keep_diagnostic(shot, 'nested_scroll_uncovered')
                result.update(status='partial', reason='nested_scroll_not_covered')
                break
            if shot.get('unstable'):
                keep_diagnostic(shot, 'layout_changed')
                unstable_attempts += 1
                if unstable_attempts >= 3:
                    result.update(status='partial', reason='layout_changed_during_capture')
                    break
                continue
            unstable_attempts = 0
            if result['shots']:
                previous = result['shots'][-1]
                if (shot['total'] != previous['total'] or shot['height'] != previous['height'] or
                        shot.get('box', {}).get('width') != previous.get('box', {}).get('width')):
                    keep_diagnostic(shot, 'layout_changed_between_segments')
                    result.update(status='partial', reason='layout_changed_between_segments')
                    break
                if shot['top'] > previous['top'] + previous['height'] + 2:
                    keep_diagnostic(shot, 'coverage_gap')
                    result.update(status='partial', reason='coverage_gap')
                    break
                if top > previous['top'] and shot['top'] <= previous['top'] and shot['top'] + shot['height'] < shot['total'] - 2:
                    keep_diagnostic(shot, 'scroll_did_not_advance')
                    result.update(status='partial', reason='scroll_did_not_advance')
                    break
            elif shot['top'] > 2:
                keep_diagnostic(shot, 'missing_top')
                missing_top_attempts += 1
                if missing_top_attempts >= 4:
                    result.update(status='partial', reason='missing_top')
                    break
                top = 0
                time.sleep(.75)
                continue
            bottom = shot['top'] + shot['height'] >= shot['total'] - 2
            stable = stable + 1 if bottom and last_total == shot['total'] else 0
            last_total = shot['total']
            if not result['shots'] or shot['top'] != result['shots'][-1]['top'] or shot['total'] != result['shots'][-1]['total']:
                filename = f"segment-{len(result['shots']):03d}.png"
                image = base64.b64decode(shot.pop('png'), validate=True)
                (folder / filename).write_bytes(image)
                result['shots'].append(dict(shot, file=filename, sha256=hashlib.sha256(image).hexdigest()))
                save_json(folder / 'manifest.json', result)
            if time.monotonic() >= deadline:
                result['reason'] = 'time_or_segment_limit'
                break
            if bottom and stable >= 3:
                result.update(status='captured_unverified', reason='bottom_stable')
                break
            top = next_scroll(shot['top'], shot['height'], shot['total'])
        else:
            result['reason'] = 'time_or_segment_limit'
        if any(s['unstable'] for s in result['shots']):
            result.update(status='partial', reason='layout_changed_during_capture')
        if result['status'] == 'captured_unverified':
            result['stitched'] = stitch(folder, result['shots'])
        after = session.call('cards')
        matching = [c for c in after if c['geek_id'] == card['id']]
        result['contact_after'] = ('contacted' if matching and any(t in matching[0]['text'] for t in ('继续沟通', '已沟通')) else 'unknown')
        result['contact_verification'] = 'pending' if card['contact_status'] == 'unknown' else ('unchanged' if result['contact_after'] == card['contact_status'] else 'changed_or_unknown')
    except Exception as exc:  # noqa: BLE001 - persist terminal probe failure without sensitive payloads
        result['status'] = 'partial'
        result['reason'] = str(exc)[:300] if isinstance(exc, (RuntimeError, BossApiError)) else type(exc).__name__
    finally:
        if capture_id:
            try:
                released = session.call('profile_capture', dict(args, action='release', capture_id=capture_id))
                result['viewport_restored'] = released.get('viewport_restored')
                if result['viewport_restored'] is False:
                    result.update(status='partial', reason='viewport_restore_unverified')
            except Exception as exc:  # noqa: BLE001
                result['release_error'] = type(exc).__name__
                result.update(status='partial', reason='viewport_restore_failed')
        result['elapsed_seconds'] = round(time.monotonic() - start, 2)
        save_json(folder / 'manifest.json', result)
    return result


def main(argv=None):
    import sys

    from .browser_session import browser_connection, select_page
    from .exceptions import BossApiError
    values = list(sys.argv[1:] if argv is None else argv)
    if '--independent' in values:
        values.remove('--independent')
        return independent_main(values)
    parser = argparse.ArgumentParser(description='Capture recommended resumes in the existing logged-in Chrome via the local extension.')
    parser.add_argument('--candidate-id', action='append', default=[])
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--browser-target')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--max-seconds', type=int, default=120)
    parser.add_argument('--max-segments', type=int, default=100)
    args = parser.parse_args(values)
    if not 1 <= args.limit <= 5 or args.max_seconds < 1 or not 1 <= args.max_segments <= 100:
        parser.error('limit must be 1..5; timeout positive; segments 1..100')
    output = args.output or Path(__file__).resolve().parents[1] / '.runtime' / 'precontact-capture' / datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=False)
    summary = {'mode': 'existing_chrome_extension', 'results': [], 'status': 'started'}
    save_json(output / 'manifest.json', summary)
    try:
        session = browser_connection()
        status = session.rpc('/status')
        page = select_page(status, session.call('discover')['pages'], args.browser_target)
        session.target, session.account_key = page['target'], page.get('account_key', '')
        session.navigate('recommend')
        seen = set()
        for index in range(args.limit):
            refreshed = session.call('navigate', {'page': 'recommend', 'refresh': True})
            session.target, session.account_key = refreshed['target'], refreshed['account_key']
            deadline = time.monotonic() + 10
            cards = []
            while time.monotonic() < deadline:
                cards = session.call('cards')
                if cards:
                    break
                time.sleep(.5)
            unique = {c['geek_id']: c for c in cards}
            if args.candidate_id:
                if index >= len(args.candidate_id):
                    break
                wanted = args.candidate_id[index]
                if wanted not in unique:
                    raise RuntimeError('requested_candidate_not_on_current_recommendations')
                c = unique[wanted]
            else:
                c = next((c for c in unique.values() if c['geek_id'] not in seen), None)
                if c is None:
                    raise RuntimeError('no_new_recommendation_cards')
            seen.add(c['geek_id'])
            card = {'id': c['geek_id'], 'name': c['name'], 'text': c['text'],
                    'contact_status': 'contacted' if any(t in c['text'] for t in ('继续沟通', '已沟通')) else 'unknown'}
            result = capture_extension(session, card, output / evidence_key(card['id']), args.max_seconds, args.max_segments, refresh=False)
            summary['results'].append(result)
            save_json(output / 'manifest.json', summary)
            if result['status'] != 'captured_unverified':
                break
        summary['status'] = 'captured_unverified' if all(r['status'] == 'captured_unverified' for r in summary['results']) else 'partial'
    except Exception as exc:  # noqa: BLE001 - persist terminal probe failure without sensitive payloads
        summary.update(status='failed', reason=str(exc)[:300] if isinstance(exc, (RuntimeError, BossApiError)) else type(exc).__name__)
    finally:
        save_json(output / 'manifest.json', summary)
        rows = ['# 推荐详情截图核对', '', '自动采集结果不等于内容完整性验收。人工核对：待完成。', '',
                '| 候选人 ID | 联系状态 | 采集状态 | 停止原因 | 分段数 |', '|---|---|---|---|---|']
        for r in summary['results']:
            rows.append(f"| {r['candidate']['id']} | {r['candidate']['contact_status']} | {r['status']} | {r['reason']} | {len(r['shots'])} |")
        rows += ['', '核对：对象身份、全部展开模块、分段连续性、最底部内容、联系状态是否改变。',
                 '联系状态 unknown 不能证明对象尚未联系。截图权限与后台兼容性单独核实。',
                 '此模式复用已有 Chrome，不代表无头模式通过；未执行 OCR 或评分。',
                 f"运行状态：{summary['status']}；原因：{summary.get('reason', '')}"]
        (output / 'verification.md').write_text('\n'.join(rows), encoding='utf-8')
        print(json.dumps({'status': summary['status'], 'output': str(output)}, ensure_ascii=False), flush=True)
    return 0 if summary['status'] == 'captured_unverified' else 2
