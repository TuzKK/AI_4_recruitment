"""Read-only local probe of rendered BOSS online-resume Canvas pages."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from boss_cli.browser_session import browser_connection, select_page
from boss_cli.exceptions import BossApiError
from boss_cli.precontact_capture import evidence_key, next_scroll, save_json


def _readable_bitmap(path):
    with Image.open(path) as source:
        rgba = source.convert('RGBA')
    background = Image.new('RGBA', rgba.size, 'white')
    background.alpha_composite(rgba)
    return background.convert('RGB')


def _continuous(previous, current, output):
    old, new = _readable_bitmap(output / previous['file']), _readable_bitmap(output / current['file'])
    try:
        old_canvas, new_canvas = previous['canvas'], current['canvas']
        if old.size != new.size or old_canvas['css_height'] != new_canvas['css_height']:
            return False
        scale = old.height / old_canvas['css_height']
        advance = round((current['top'] - previous['top']) * scale)
        overlap = old.height - advance
        if advance <= 0 or overlap < 30:
            return False
        difference = ImageChops.difference(old.crop((0, advance, old.width, old.height)),
                                           new.crop((0, 0, new.width, overlap)))
        return max(ImageStat.Stat(difference).mean) <= 5
    finally:
        old.close()
        new.close()


def _stitch_scrolled(output, pages, total):
    first = pages[0]
    scale = first['canvas']['height'] / first['canvas']['css_height']
    size = (first['canvas']['width'], round(total * scale))
    if size[0] * size[1] > 100_000_000:
        raise RuntimeError('stitched_image_too_large')
    image = Image.new('RGB', size, 'white')
    for page in pages:
        part = _readable_bitmap(output / page['file'])
        try:
            image.paste(part, (0, round(page['top'] * scale)))
        finally:
            part.close()
    image.save(output / 'resume-long.png')


def capture_scrolled_canvas(session, geek_id, capture_id, region, inspect, output, manifest, max_segments):
    """Retain every raw bitmap; only stitch if its measured overlap is continuous."""
    if inspect['canvas_count'] != 1:
        raise RuntimeError('scroll_canvas_count_not_one')
    if region['total'] <= region['height'] + 2:
        raise RuntimeError('outer_resume_not_scrollable')
    if region['top'] != 0:
        raise RuntimeError('outer_resume_not_at_top')
    manifest['scroll_region'] = {k: region[k] for k in ('top', 'height', 'total', 'frame_url')}
    top = 0
    for index in range(max_segments):
        response = session.call('resume_canvas', {'geek_id': geek_id, 'action': 'segment',
                                                  'capture_id': capture_id, 'top': top})
        if response['top'] != top or response['height'] != region['height'] or response['total'] != region['total']:
            raise RuntimeError('scroll_geometry_changed')
        raw = base64.b64decode(response['png'], validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            if image.size != (response['canvas']['width'], response['canvas']['height']):
                raise RuntimeError('canvas_image_size_mismatch')
        filename = f'canvas-{index:03d}.png'
        (output / filename).write_bytes(raw)
        manifest['pages'].append({'file': filename, 'top': top, 'height': response['height'],
                                  'total': response['total'], 'canvas': response['canvas'],
                                  'sha256': hashlib.sha256(raw).hexdigest()})
        save_json(output / 'manifest.json', manifest)
        if index and manifest['pages'][-1]['sha256'] == manifest['pages'][-2]['sha256']:
            raise RuntimeError('canvas_did_not_change_after_scroll')
        if index and not _continuous(manifest['pages'][-2], manifest['pages'][-1], output):
            raise RuntimeError('canvas_scroll_overlap_mismatch')
        if top + region['height'] >= region['total'] - 2:
            if top + response['canvas']['css_height'] < region['total'] - 2:
                raise RuntimeError('canvas_does_not_cover_outer_bottom')
            _stitch_scrolled(output, manifest['pages'], region['total'])
            manifest['stitched'] = 'resume-long.png'
            manifest.update(status='canvas_segments_unverified', reason='outer_scroll_bottom_reached')
            return
        following = next_scroll(top, min(region['height'], response['canvas']['css_height']), region['total'])
        if following <= top:
            raise RuntimeError('scroll_did_not_advance')
        top = following
    raise RuntimeError('canvas_segment_limit')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Export only rendered online-resume Canvas pages in the existing Chrome')
    parser.add_argument('--browser-target')
    parser.add_argument('--candidate-id')
    parser.add_argument('--max-pages', type=int, default=15)
    parser.add_argument('--scroll', action='store_true', help='export each outer-scroll position using the rendered Canvas')
    args = parser.parse_args(argv)
    if not 1 <= args.max_pages <= 30:
        parser.error('max-pages must be 1..30')
    output = ROOT / '.runtime' / 'precontact-canvas' / datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'mode': 'existing_chrome_rendered_canvas', 'status': 'partial', 'reason': 'not_started',
                'pages': [], 'manual_review': 'pending'}
    save_json(output / 'manifest.json', manifest)
    capture_id = None
    try:
        session = browser_connection()
        status = session.rpc('/status')
        page = select_page(status, session.call('discover')['pages'], args.browser_target)
        session.target, session.account_key = page['target'], page['account_key']
        refreshed = session.call('navigate', {'page': 'recommend', 'refresh': True})
        session.target, session.account_key = refreshed['target'], refreshed['account_key']
        cards = []
        for _ in range(20):
            cards = session.call('cards')
            if cards:
                break
            time.sleep(.5)
        unique = {c['geek_id']: c for c in cards}
        if args.candidate_id and args.candidate_id not in unique:
            raise RuntimeError('requested_candidate_not_on_current_recommendations')
        card = unique.get(args.candidate_id) if args.candidate_id else next(iter(unique.values()), None)
        if card is None:
            raise RuntimeError('no_recommendation_cards')
        geek_id = card['geek_id']
        manifest['candidate_key'] = evidence_key(geek_id)
        manifest['contact_before'] = ('contacted' if any(t in card['text'] for t in ('继续沟通', '已沟通')) else 'unknown')
        session.call('open_profile', {'geek_id': geek_id})
        time.sleep(2)
        # Preparing the real detail scroll region can trigger lazy Canvas rendering.
        try:
            warmup = session.call('profile_capture', {'geek_id': geek_id, 'action': 'prepare'})
            capture_id = warmup['capture_id']
            if not args.scroll:
                session.call('profile_capture', {'geek_id': geek_id, 'action': 'release',
                                                 'capture_id': capture_id})
                capture_id = None
        except BossApiError as exc:
            if 'verification_required' in str(exc):
                raise
            manifest['warmup_error'] = type(exc).__name__
        except Exception as exc:  # noqa: BLE001 - Canvas probe still records its own result
            manifest['warmup_error'] = type(exc).__name__
        inspect = None
        ready = False
        for attempt in range(2):
            try:
                inspect = session.call('resume_canvas', {'geek_id': geek_id, 'action': 'inspect'})
                ready = bool(inspect.get('initialized')) and bool(inspect['canvas_count']) and all(
                    c['width'] >= 400 and c['height'] >= 400
                    for c in inspect['canvases']
                )
                if ready:
                    break
            except BossApiError as exc:
                if 'verification_required' in str(exc):
                    raise
                manifest['readiness_error'] = type(exc).__name__
            except Exception as exc:  # noqa: BLE001 - detail may still be rendering
                manifest['readiness_error'] = type(exc).__name__
            if attempt == 0:
                time.sleep(2)
        if not ready:
            if inspect:
                manifest['canvas_observed'] = inspect['canvases']
                manifest['pixel_stats'] = inspect.get('pixel_stats')
                manifest['stable_count'] = inspect.get('stable_count')
                if inspect['canvas_count']:
                    try:
                        response = session.call('resume_canvas', {'geek_id': geek_id, 'action': 'diagnostic', 'index': 0})
                        raw = base64.b64decode(response['png'], validate=True)
                        with Image.open(io.BytesIO(raw)) as image:
                            image.verify()
                        filename = 'diagnostic-canvas-000.png'
                        (output / filename).write_bytes(raw)
                        manifest['diagnostics'] = [{'file': filename, 'canvas': response['canvas'],
                                                    'unstable': response['unstable'],
                                                    'sha256': hashlib.sha256(raw).hexdigest()}]
                    except Exception as exc:  # noqa: BLE001 - diagnostic never upgrades readiness
                        manifest['diagnostic_error'] = type(exc).__name__
            raise RuntimeError('resume_canvas_not_initialized')
        manifest['frame'] = {k: v for k, v in inspect.items() if k not in ('canvases', 'document_id')}
        manifest['canvas_layout'] = inspect['canvases']
        manifest['canvas_count'] = inspect['canvas_count']
        manifest['reason'] = 'canvas_export_in_progress'
        save_json(output / 'manifest.json', manifest)
        if args.scroll:
            if not capture_id:
                raise RuntimeError('outer_scroll_region_not_prepared')
            capture_scrolled_canvas(session, geek_id, capture_id, warmup, inspect, output, manifest, args.max_pages)
            after = session.call('cards')
            same = [c for c in after if c['geek_id'] == geek_id]
            manifest['contact_after'] = ('contacted' if same and any(t in same[0]['text'] for t in ('继续沟通', '已沟通')) else 'unknown')
            return 0
        if inspect['canvas_count'] > args.max_pages:
            raise RuntimeError('canvas_page_limit')
        for index in range(inspect['canvas_count']):
            response = session.call('resume_canvas', {'geek_id': geek_id, 'action': 'image', 'index': index})
            if (response['document_id'] != inspect['document_id'] or response['canvas_count'] != inspect['canvas_count']
                    or response['identity'] != inspect['identity']):
                raise RuntimeError('canvas_document_changed')
            raw = base64.b64decode(response['png'], validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                if image.size != (response['canvas']['width'], response['canvas']['height']):
                    raise RuntimeError('canvas_image_size_mismatch')
            filename = f'canvas-{index:03d}.png'
            (output / filename).write_bytes(raw)
            manifest['pages'].append({'file': filename, 'canvas': response['canvas'],
                                      'sha256': hashlib.sha256(raw).hexdigest()})
            save_json(output / 'manifest.json', manifest)
        after = session.call('cards')
        same = [c for c in after if c['geek_id'] == geek_id]
        manifest['contact_after'] = ('contacted' if same and any(t in same[0]['text'] for t in ('继续沟通', '已沟通')) else 'unknown')
        manifest.update(status='canvas_pages_unverified', reason='all_rendered_canvases_exported')
    except Exception as exc:  # noqa: BLE001 - retain partial evidence without candidate text
        manifest.update(status='partial', reason=str(exc)[:200] if isinstance(exc, (RuntimeError, BossApiError)) else type(exc).__name__)
    finally:
        if capture_id:
            try:
                session.call('profile_capture', {'geek_id': geek_id, 'action': 'release', 'capture_id': capture_id})
            except Exception:  # noqa: BLE001 - preserve captured evidence and report release uncertainty
                manifest['release_unverified'] = True
        save_json(output / 'manifest.json', manifest)
        (output / 'verification.md').write_text(
            '# 在线简历 Canvas 本地核对\n\n逐页核对对象、内容顺序、页间间隙、个人介绍是否展开以及最底部。'
            '\nCanvas 导出只证明已渲染像素可得，不证明联系前完整简历或 OCR 已通过。\n'
            f"\n状态：{manifest['status']}；原因：{manifest['reason']}；图片数：{len(manifest['pages'])}。\n",
            encoding='utf-8')
        print(json.dumps({'status': manifest['status'], 'output': str(output)}, ensure_ascii=False), flush=True)
    return 0 if manifest['status'] == 'canvas_pages_unverified' else 2


if __name__ == '__main__':
    raise SystemExit(main())
