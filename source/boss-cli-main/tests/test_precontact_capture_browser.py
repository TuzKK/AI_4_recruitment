import json

import pytest

sync_playwright = pytest.importorskip('playwright.sync_api').sync_playwright

from boss_cli.precontact_capture import capture

# The same page behavior occurs in both plain DOM and canvas/iframe resumes.
HTML = """<div data-geekid="one"><div class="name">Example Candidate</div><div class="info">A long enough recommendation card with experience and skills</div></div>
<script>document.querySelector('.name').onclick=()=>{
const modal=document.createElement('div');modal.className='boss-dialog__body';
modal.innerHTML='<iframe src="https://fixture.invalid/c-resume" style="width:600px;height:400px;border:0"></iframe>';
document.body.appendChild(modal);};</script>"""
RESUME = """<style>body{margin:0}.scroll{height:400px;overflow:auto;width:600px}canvas{display:block}</style>
<div class="scroll"><canvas width="600" height="2200"></canvas></div>
<script>const c=document.querySelector('canvas'),x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,600,2200);
x.fillStyle='black';x.font='20px sans-serif';for(let i=0;i<55;i++)x.fillText('Experience section '+i,30,i*40+30);</script>"""


def test_canvas_iframe_captures_bottom_and_keeps_originals(tmp_path):
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.route('https://fixture.invalid/c-resume',lambda r:r.fulfill(body=RESUME,content_type='text/html'))
        page.set_content(HTML)
        result=capture(page,{'id':'one','contact_status':'unknown'},tmp_path/'one',30,100)
        browser.close()
    assert result['status']=='captured_unverified', result
    assert result['shots'][-1]['top']==1800
    assert len(result['shots'])>5
    assert result['stitched']=='resume-long.png'
    assert all((tmp_path/'one'/s['file']).exists() for s in result['shots'])
    assert json.loads((tmp_path/'one'/'manifest.json').read_text())['manual_review']=='pending'


def test_segment_limit_is_partial(tmp_path):
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.route('https://fixture.invalid/c-resume',lambda r:r.fulfill(body=RESUME,content_type='text/html'))
        page.set_content(HTML)
        result=capture(page,{'id':'one'},tmp_path/'one',30,1)
        browser.close()
    assert result['status']=='partial'
    assert result['reason']=='time_or_segment_limit'


def test_extension_scroll_function_handles_canvas_frame(tmp_path):
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'chrome-extension' / 'capture.mjs').read_text(encoding='utf-8')
    function = source.split('export async function capturePage', 1)[1].split('export async function profileCapture', 1)[0]
    expression = '(async function capturePage' + function.strip() + ')'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.route('https://fixture.invalid/c-resume', lambda r: r.fulfill(body=RESUME, content_type='text/html'))
        page.goto('https://fixture.invalid/c-resume')
        # Run exactly the function serialized by the extension, rather than a duplicate.
        import time
        prepare = page.evaluate('async ([fn,deadline]) => await eval(fn)("prepare",null,deadline)', [expression, int(time.time()*1000)+10000])
        assert prepare['total'] == 2200
        shot = page.evaluate('async ([fn,deadline]) => await eval(fn)("step",1800,deadline)', [expression, int(time.time()*1000)+10000])
        assert shot['top'] == 1800
        assert shot['box']['height'] == 400
        assert shot['canvas_count'] == 1
        browser.close()


def test_extension_can_probe_textless_resume_viewport():
    import time
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'chrome-extension' / 'capture.mjs').read_text(encoding='utf-8')
    function = source.split('export async function capturePage', 1)[1].split('export async function profileCapture', 1)[0]
    expression = '(async function capturePage' + function.strip() + ')'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 600, 'height': 400})
        page.route('https://fixture.invalid/c-resume', lambda r: r.fulfill(body='<body></body>', content_type='text/html'))
        page.goto('https://fixture.invalid/c-resume')
        result = page.evaluate('async ([fn,deadline])=>await eval(fn)("prepare",null,deadline)', [expression, int(time.time()*1000)+10000])
        assert result is not None
        assert result['height'] == 400
        assert result['canvas_count'] == 0
        browser.close()


def test_extension_tracks_outer_resume_scroll_container():
    import time
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'chrome-extension' / 'capture.mjs').read_text(encoding='utf-8')
    function = source.split('export async function capturePage', 1)[1].split('export async function profileCapture', 1)[0]
    expression = '(async function capturePage' + function.strip() + ')'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width':800,'height':600})
        page.set_content('<div class="dialog-lib-resume"><div style="height:400px;width:600px;overflow:auto"><iframe style="height:2200px;width:590px" srcdoc="long resume content"></iframe></div></div>')
        result = page.evaluate('async ([fn,deadline])=>await eval(fn)("prepare",null,deadline)',[expression,int(time.time()*1000)+10000])
        assert result['contains_iframe'] is True
        assert result['height'] == 400
        assert result['total'] >= 2200
        next_result = page.evaluate('async ([fn,deadline])=>await eval(fn)("step",320,deadline)',[expression,int(time.time()*1000)+10000])
        assert next_result['top'] == 320
        browser.close()


def test_browser_capture_beyond_viewport_keeps_iframe_bottom_pixels(tmp_path):
    import base64
    import io
    from pathlib import Path

    from PIL import Image
    source = (Path(__file__).resolve().parents[1]/'chrome-extension'/'capture.mjs').read_text(encoding='utf-8')
    assert 'export function screenshotRequest' in source
    function = source.split('export function screenshotRequest',1)[1].split('export ',1)[0]
    expression = '(function screenshotRequest'+function.strip()+')'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome',headless=True)
        page = browser.new_page(viewport={'width':900,'height':600})
        page.set_content("""<body style="margin:0"><div style="height:40px"></div><iframe style="border:0;width:500px;height:580px" srcdoc="<body style='margin:0;height:580px;background:white'><div style='position:absolute;top:560px;height:20px;width:100%;background:rgb(255,0,255)'></div></body>"></iframe></body>""")
        page.wait_for_timeout(300)
        params = page.evaluate(expression,{'x':0,'y':40,'width':500,'height':580,'scale':1})
        result = page.context.new_cdp_session(page).send('Page.captureScreenshot',params)
        image = Image.open(io.BytesIO(base64.b64decode(result['data']))).convert('RGB')
        assert image.size == (500,580)
        assert image.getpixel((200,570)) == (255,0,255)
        browser.close()


def test_fit_resume_viewport_preserves_scroll_range_and_restores_style():
    import time
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'chrome-extension'/'capture.mjs').read_text(encoding='utf-8')
    assert 'export async function fitCaptureViewport' in source
    fit=source.split('export async function fitCaptureViewport',1)[1].split('export ',1)[0]
    restore=source.split('export function restoreCaptureViewport',1)[1].split('export ',1)[0]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':800,'height':600})
        page.set_content('<div data-precontact-scroll="true" style="height:580px;min-height:580px;overflow:auto;width:500px"><div style="height:2200px">Resume</div></div>')
        before=page.locator('[data-precontact-scroll]').get_attribute('style')
        result=page.evaluate('(async function'+fit.strip()+')',[560,'test',int(time.time()*1000)+10000])
        assert result['height']==560
        assert result['total']==2200
        page.evaluate('(function'+restore.strip()+')',['test'])
        assert page.locator('[data-precontact-scroll]').get_attribute('style')==before
        browser.close()

