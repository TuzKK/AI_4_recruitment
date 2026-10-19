"""Local Chrome discovery, read-only account inspection and CDP attachment.

Like boss-resume-filter, attach through a debugging port or use a separate
profile. Never stop the user's Chrome or copy its authentication database.
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from playwright.async_api import async_playwright

RECOMMEND_URL = 'https://www.zhipin.com/web/chat/recommend'
PROFILES_BASE = Path(__file__).resolve().parents[1] / 'data' / 'boss_profiles'


def browser_mode(config: dict) -> bool:
    return platform.system() != 'Darwin' or config.get('rpa_mode', 'auto') != 'mac_app'


def normalize_endpoint(value: str) -> str:
    u = urlsplit(value.strip())
    if (u.scheme != 'http' or u.hostname not in ('localhost', '127.0.0.1')
            or u.username or u.password or u.path not in ('', '/') or u.query or u.fragment
            or not u.port or not 1 <= u.port <= 65535):
        raise ValueError('仅支持本机 Chrome 地址，例如 http://127.0.0.1:9222')
    return f'http://127.0.0.1:{u.port}'


def is_boss_url(value: str) -> bool:
    u = urlsplit(value)
    return u.scheme == 'https' and u.hostname in ('www.zhipin.com', 'zhipin.com')


def find_chrome(configured: str = '') -> str:
    if configured:
        if Path(configured).is_file():
            return configured
        # Old upstream default is macOS-only. Ignore it on other platforms.
        if platform.system() == 'Darwin' or not configured.startswith('/Applications/'):
            raise FileNotFoundError('配置的 Chrome 路径不存在，请检查 config.yaml 的 browser.chrome_path')
    paths = []
    for key in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        if os.environ.get(key):
            paths.append(Path(os.environ[key]) / 'Google/Chrome/Application/chrome.exe')
    paths.append(Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chrome'):
        found = shutil.which(name)
        if found:
            paths.append(Path(found))
    for p in paths:
        if p.is_file():
            return str(p)
    raise FileNotFoundError('未找到 Google Chrome，请安装 Chrome 或设置 browser.chrome_path')


def process_ports() -> tuple[set[int], int]:
    """Inspect main Chrome processes; return ports and ordinary window count."""
    ports, ordinary = set(), 0
    if platform.system() != 'Windows':
        return ports, ordinary
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
         "@(Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
         "Where-Object { $_.CommandLine -notmatch '--type=' } | "
         "Select-Object -ExpandProperty CommandLine) | ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=8,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    commands = json.loads(result.stdout.strip() or '[]')
    if isinstance(commands, str):
        commands = [commands]
    for cmd in commands:
        match = re.search(r'--remote-debugging-port(?:=|\s+)(\d+)', cmd or '')
        if not match:
            ordinary += 1
            continue
        port = int(match[1])
        if port:
            ports.add(port)
        else:
            profile = re.search(r'--user-data-dir(?:=|\s+)(?:"([^"]+)"|([^\s"]+))', cmd)
            if profile:
                port = profile_port(Path(profile[1] or profile[2]))
                if port:
                    ports.add(port)
    return ports, ordinary


def profile_port(profile: Path) -> int | None:
    try:
        port = int((profile / 'DevToolsActivePort').read_text().splitlines()[0])
        return port if 1 <= port <= 65535 else None
    except (OSError, ValueError, IndexError):
        return None


def profile_matches_version(profile: Path, version: dict) -> bool:
    try:
        lines = (profile / 'DevToolsActivePort').read_text().splitlines()
        websocket = urlsplit(version.get('webSocketDebuggerUrl', ''))
        return len(lines) >= 2 and websocket.path == lines[1] and websocket.port == int(lines[0])
    except (OSError, ValueError, IndexError):
        return False


async def target_id(page) -> str:
    session = await page.context.new_cdp_session(page)
    try:
        return (await session.send('Target.getTargetInfo'))['targetInfo']['targetId']
    finally:
        await session.detach()


async def inspect_page(page) -> dict:
    """URL alone never proves authentication. Inspect visible recruiter DOM."""
    result = {'state': 'unknown', 'name': '', 'company': ''}
    if page.is_closed() or not is_boss_url(page.url):
        return {**result, 'state': 'wrong_page'}
    path = urlsplit(page.url).path
    if any(x in path for x in ('/login', '/web/user/')):
        return {**result, 'state': 'not_logged_in'}
    if any(x in path for x in ('/verify', '/captcha', '/safe/')):
        return {**result, 'state': 'verification_required'}
    if '/web/geek/' in path:
        return {**result, 'state': 'wrong_role'}
    recruiter = path.startswith('/web/chat') or path.startswith('/web/boss')
    authenticated = False
    for frame in page.frames:
        # Same-site subframes only; never inspect unrelated embedded pages.
        if frame != page.main_frame and not is_boss_url(frame.url):
            continue
        data = await frame.evaluate('''() => {
          const visible = el => !!el && !!(el.getClientRects().length) &&
            getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
          const any = sel => [...document.querySelectorAll(sel)].some(visible);
          const text = sel => [...document.querySelectorAll(sel)].filter(visible)[0]?.textContent?.trim().slice(0, 100) || '';
          return {
            verify: any('.geetest_panel, .geetest_holder, .verify-dialog, #captcha'),
            login: any('.login-dialog, .login-register-box, .sign-form'),
            content: any('.recommend-main, .boss-chat, .resume-list, li.card-item, .chat-container, .chat-conversation'),
            name: text('.nav-figure .nav-name, .nav-figure .name, .boss-name'),
            company: text('.nav-figure .nav-company')
          };
        }''')
        if data['verify']:
            return {**result, 'state': 'verification_required'}
        if data['login']:
            return {**result, 'state': 'not_logged_in'}
        authenticated = authenticated or data['content'] or bool(data['name'])
        result['name'] = result['name'] or data['name']
        result['company'] = result['company'] or data['company']
    result['state'] = 'logged_in' if recruiter and authenticated else 'unknown'
    return result


async def inspect_during_login(page):
    """A login redirect can invalidate a frame between enumeration and evaluation."""
    from playwright.async_api import Error as PlaywrightError
    try:
        return await inspect_page(page)
    except PlaywrightError as exc:
        if any(hint in str(exc).lower() for hint in ('execution context was destroyed', 'frame was detached', 'frame has been detached')):
            return {'state': 'unknown', 'name': '', 'company': ''}
        raise


class ChromeConnection:
    def __init__(self, endpoint: str, selected_target: str = ''):
        self.endpoint = normalize_endpoint(endpoint)
        self.selected_target = selected_target
        self.pw = self.browser = self.page = None

    async def open(self):
        try:
            self.pw = await async_playwright().start()
            self.browser = await self.pw.chromium.connect_over_cdp(self.endpoint, timeout=5000)
            matches = []
            for context in self.browser.contexts:
                for page in context.pages:
                    if is_boss_url(page.url) and (not self.selected_target or await target_id(page) == self.selected_target):
                        matches.append(page)
            if len(matches) != 1:
                raise RuntimeError('BOSS 页面已关闭或存在多个页面，请重新检测并选择要接入的页面')
            self.page = matches[0]
            return self.page
        except BaseException:
            await self.close()
            raise

    async def close(self):
        # Stop only our client connection, not Chrome or the user's tabs.
        if self.pw:
            await self.pw.stop()
            self.pw = None


async def probe_endpoint(endpoint: str) -> list[dict]:
    endpoint = normalize_endpoint(endpoint)
    async with httpx.AsyncClient(trust_env=False, timeout=1.0) as client:
        version = (await client.get(endpoint + '/json/version')).json()
        if not version.get('webSocketDebuggerUrl'):
            return []
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(endpoint, timeout=4000)
        found = []
        for context in browser.contexts:
            for page in context.pages:
                if is_boss_url(page.url):
                    try:
                        state = await inspect_page(page)
                        found.append({**state, 'cdp_url': endpoint, 'target_id': await target_id(page),
                                      'url': 'https://www.zhipin.com' + urlsplit(page.url).path})
                    except Exception:
                        continue  # A tab may disappear during discovery.
        return found
    finally:
        await pw.stop()


async def discover(saved: list[str], port: int | None = None) -> dict:
    warning = ''
    try:
        ports, ordinary = await asyncio.to_thread(process_ports)
    except Exception:
        ports, ordinary = set(), 0
        warning = '无法读取 Chrome 进程，可填写调试端口检测。'
    ports.add(9222)
    if port:
        ports.add(port)
    for profile in PROFILES_BASE.glob('*/DevToolsActivePort'):
        p = profile_port(profile.parent)
        if p:
            ports.add(p)
    urls = {f'http://127.0.0.1:{p}' for p in ports}
    for endpoint in saved:
        if endpoint:
            try:
                urls.add(normalize_endpoint(endpoint))
            except ValueError:
                pass
    semaphore = asyncio.Semaphore(4)
    async def probe(url):
        async with semaphore:
            try:
                return await asyncio.wait_for(probe_endpoint(url), timeout=8)
            except Exception:
                return []
    results = await asyncio.gather(*(probe(url) for url in sorted(urls)))
    return {'pages': [p for group in results for p in group],
            'ordinary_chrome_count': ordinary, 'warning': warning}


async def launch_managed(profile: str, configured: str = '') -> str:
    folder = Path(profile).resolve()
    if not folder.is_relative_to(PROFILES_BASE.resolve()) or folder == PROFILES_BASE.resolve():
        raise ValueError('账号浏览器目录不在项目管理范围内')
    folder.mkdir(parents=True, exist_ok=True)
    old_port = profile_port(folder)
    if old_port:
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=1) as client:
                resp = await client.get(f'http://127.0.0.1:{old_port}/json/version')
                if resp.status_code == 200 and profile_matches_version(folder, resp.json()):
                    return f'http://127.0.0.1:{old_port}'
        except httpx.HTTPError:
            pass
    # Visible because the user requested an interactive browser for login.
    subprocess.Popen([find_chrome(configured), '--remote-debugging-port=0',
                      '--remote-debugging-address=127.0.0.1', f'--user-data-dir={folder}',
                      '--no-first-run', '--no-default-browser-check', RECOMMEND_URL],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        await asyncio.sleep(.25)
        port = profile_port(folder)
        if port:
            try:
                async with httpx.AsyncClient(trust_env=False, timeout=1) as client:
                    resp = await client.get(f'http://127.0.0.1:{port}/json/version')
                    if resp.status_code == 200 and profile_matches_version(folder, resp.json()):
                        return f'http://127.0.0.1:{port}'
            except httpx.HTTPError:
                pass
    raise RuntimeError('Chrome 调试连接未就绪，请关闭该专用窗口后重试；普通 Chrome 无需关闭')
