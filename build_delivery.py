from pathlib import Path
import shutil, fnmatch, json, hashlib, ast

root = Path(__file__).resolve().parent
dest = root / 'RECRUITMENT_DELIVERY_20261012'
dest.mkdir(exist_ok=False)
skip_dirs = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.runtime', '.pytest_cache', '.ruff_cache', '.mypy_cache', '.storage', '.chrome_profile', '.idea', '.vscode', '.agent', '.agents', '.codex', 'build', 'backups', 'resumes', 'output'}
skip_files = ['.env', '.env.local', '*.pyc', '*.pyo', '*.log', '*.db', '*.db-*', '*.sqlite*', '*.private.*', '*.tsbuildinfo', '*.zip', '*.whl', '*.local.json', '*.bak', 'browser_bridge_token', 'candidates_all*', 'contact_queue.json*', '.DS_Store']
omitted = []
for project in (root / 'source').iterdir():
    if not project.is_dir(): continue
    def ignore(folder, names):
        ignored = []
        rel = Path(folder).relative_to(project)
        for name in names:
            p = Path(folder) / name
            reject = (p.is_dir() and name in skip_dirs) or any(fnmatch.fnmatch(name, pattern) for pattern in skip_files)
            reject |= project.name == 'Boss-main' and (rel.as_posix(), name) in [('backend', 'data'), ('.', 'docs')]
            reject |= project.name == 'boss-cli-main' and name in {'dist', 'docs'} and rel == Path('.')
            reject |= project.name.startswith('boss-resume-filter-') and name in {'input.txt', 'api_config.json'} and rel == Path('.')
            if reject:
                ignored.append(name)
                omitted.append(str(p.relative_to(root)))
        return ignored
    shutil.copytree(project, dest / 'source' / project.name, ignore=ignore)

cli = dest / 'source/boss-cli-main'
(cli / 'examples').mkdir()
for name in ('fetch_resume_batch.py', 'clean_resume_batch.py'):
    shutil.copy2(root / 'source/boss-cli-main/.runtime' / name, cli / 'examples' / name)
(cli / 'examples/README.md').write_text('历史批量读取和清洗示例，不是开箱即用命令。未包含真实候选人数据。运行前需自行准备 inbox.private.json，并修改批次目录和目标范围；优先使用 recruiter resume-download 正式命令。\n', encoding='utf-8')

readme = '''# 招聘项目本地交付包

这是三个独立项目的源码交付目录，包含本地改造。不是已经打通的三层招聘 Agent，也不是离线免安装的 EXE。
已排除 node_modules、虚拟环境、运行数据库、Chrome 登录资料、配对令牌、真实简历和聊天记录；请使用自己的账号与模型配置。

## 环境

Windows 10/11，Python 3.11（包含 pip、venv、Tkinter）、Chrome，首次安装需要联网。
Boss-main 已附构建后的 frontend/dist，直接运行不需要 Node.js；修改前端才需要 Node.js 与 npm ci / npm run build。
三个项目互相独立，按需要安装。以下命令均从本交付目录开始执行。

## 1. BOSS-cli：读取与导出

```powershell
cd source/boss-cli-main
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install .
powershell -ExecutionPolicy Bypass -File .\\start-browser-bridge.ps1
```

保持终端运行。在 Chrome 登录自己的 BOSS 招聘账号。打开 chrome://extensions，启用开发者模式，加载本项目 chrome-extension 文件夹。
在扩展中输入端口 17891 和终端刚显示的配对令牌，点击连接。不要使用原电脑的令牌。
在另一个 PowerShell 窗口进入同一个项目目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\\boss.ps1 browser status --probe
powershell -ExecutionPolicy Bypass -File .\\boss.ps1 --transport browser browser cards
powershell -ExecutionPolicy Bypass -File .\\boss.ps1 --transport browser recruiter inbox --page 1 --json
powershell -ExecutionPolicy Bypass -File .\\boss.ps1 recruiter resume-download --help
powershell -ExecutionPolicy Bypass -File .\\boss.ps1 recruiter chat --help
```

简历/聊天命令需要本账号接口返回的真实 ID、职位 ID、安全上下文等，姓名不能替代 ID。
默认只读；已验证的读取能力不代表所有账号全部信息可读。推荐完整简历与真实消息发送尚未打通。聊天历史需要分页，在线简历 Markdown 不等于 PDF 附件。

## 2. Boss-main：Web 平台

```powershell
cd source/Boss-main/backend
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m playwright install chromium
Copy-Item .env.example .env
```

编辑 .env，填写自己的模型 API Key、Base URL、模型名，然后运行：

```powershell
.\\.venv\\Scripts\\python.exe main.py serve --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000/settings，按项目 WINDOWS_CHROME.md 安装该项目自己的扩展并配对。
它与 BOSS-cli 的扩展/端口不同。不要把界面能启动视为全部招聘功能通过验证；详见项目中的功能边界说明。

## 3. boss-resume-filter：桌面筛选器

进入 source 下以 boss-resume-filter- 开头的目录：

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe gui_main.py
```

在界面中配置岗位、连接 Chrome、登录 BOSS；需要 AI 时设置自己的模型。已排除本机 api_config.json，首次使用自行配置。

## 交付验证与限制

frontend/dist 由本次 npm run build 成功生成；具体检查记录见 VALIDATION.md。
依赖未打包，首次安装需要下载。没有在另一台全新电脑上验证，平台接口、账号权限与页面变化可能影响业务功能。
原始项目保持不动。OMITTED.json 记录排除路径，MANIFEST.sha256.json 记录文件校验值。
各项目现有许可/署名文件保留；本目录不是官方 BOSS 产品。
'''
(dest / 'README.md').write_text(readme, encoding='utf-8-sig')
(dest / 'OMITTED.json').write_text(json.dumps(omitted, ensure_ascii=False, indent=2), encoding='utf-8')
count = 0
for p in (dest / 'source').rglob('*.py'):
    ast.parse(p.read_bytes(), filename=str(p)); count += 1
for p in dest.rglob('*'):
    assert p.name not in skip_dirs, p
    assert p.name != '.env' and not fnmatch.fnmatch(p.name, '*.private.*'), p
assert (dest / 'source/Boss-main/frontend/dist/index.html').is_file()
(dest / 'VALIDATION.md').write_text(f'# 交付检查\n\n- 前端 npm run build 成功。\n- {count} 个 Python 文件语法解析通过。\n- 无 node_modules、虚拟环境、.runtime、真实 .env 与 private 数据文件。\n- 保留已构建的前端静态文件。\n- 未执行真实发送，也未完成异机全新依赖安装测试。\n', encoding='utf-8')
manifest = {p.relative_to(dest).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()}
(dest / 'MANIFEST.sha256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'directory': str(dest), 'files': len(manifest)+1, 'python_syntax_checked': count, 'bytes': sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())}))
