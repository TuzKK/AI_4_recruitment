# 招聘项目本地交付包

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
.\.venv\Scripts\python.exe -m pip install .
powershell -ExecutionPolicy Bypass -File .\start-browser-bridge.ps1
```

保持终端运行。在 Chrome 登录自己的 BOSS 招聘账号。打开 chrome://extensions，启用开发者模式，加载本项目 chrome-extension 文件夹。
在扩展中输入端口 17891 和终端刚显示的配对令牌，点击连接。不要使用原电脑的令牌。
在另一个 PowerShell 窗口进入同一个项目目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\boss.ps1 browser status --probe
powershell -ExecutionPolicy Bypass -File .\boss.ps1 --transport browser browser cards
powershell -ExecutionPolicy Bypass -File .\boss.ps1 --transport browser recruiter inbox --page 1 --json
powershell -ExecutionPolicy Bypass -File .\boss.ps1 recruiter resume-download --help
powershell -ExecutionPolicy Bypass -File .\boss.ps1 recruiter chat --help
```

简历/聊天命令需要本账号接口返回的真实 ID、职位 ID、安全上下文等，姓名不能替代 ID。
默认只读；已验证的读取能力不代表所有账号全部信息可读。推荐完整简历与真实消息发送尚未打通。聊天历史需要分页，在线简历 Markdown 不等于 PDF 附件。

## 2. Boss-main：Web 平台

```powershell
cd source/Boss-main/backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
```

编辑 .env，填写自己的模型 API Key、Base URL、模型名，然后运行：

```powershell
.\.venv\Scripts\python.exe main.py serve --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000/settings，按项目 WINDOWS_CHROME.md 安装该项目自己的扩展并配对。
它与 BOSS-cli 的扩展/端口不同。不要把界面能启动视为全部招聘功能通过验证；详见项目中的功能边界说明。

## 3. boss-resume-filter：桌面筛选器

进入 source 下以 boss-resume-filter- 开头的目录：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe gui_main.py
```

在界面中配置岗位、连接 Chrome、登录 BOSS；需要 AI 时设置自己的模型。已排除本机 api_config.json，首次使用自行配置。

## 交付验证与限制

frontend/dist 由本次 npm run build 成功生成；具体检查记录见 VALIDATION.md。
依赖未打包，首次安装需要下载。没有在另一台全新电脑上验证，平台接口、账号权限与页面变化可能影响业务功能。
原始项目保持不动。OMITTED.json 记录排除路径，MANIFEST.sha256.json 记录文件校验值。
各项目现有许可/署名文件保留；本目录不是官方 BOSS 产品。
