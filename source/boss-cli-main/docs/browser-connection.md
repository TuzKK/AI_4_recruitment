# 连接当前已登录的 Chrome

本地扩展让 BOSS-cli 使用 Chrome 页面中的会话，不导出 BOSS Cookie。当前只读服务不能打招呼或发送消息。

## 第一次连接

1. 保持当前 BOSS 招聘页面打开。
2. 在 Chrome 地址栏输入 `chrome://extensions`，打开右上角“开发者模式”。
3. 点击“加载已解压的扩展程序”，选择 `E:\automatic_recruitment\source\boss-cli-main\chrome-extension`。选择整个文件夹，不是 manifest.json 文件。
4. 页面出现“BOSS CLI 本地连接器”后，点击 Chrome 右上角拼图图标，再点击该扩展。
5. 端口填写 `17891`。
6. 用记事本打开项目下 `.runtime\bridge.log`，复制“配对令牌”后面的整段字符，填入扩展的令牌框。不要复制标签文字，不要把令牌发到聊天里。
7. 点击“连接”。成功时显示“已连接 CLI”。如果已经加载过扩展，代码更新后在扩展管理页面点击其重新加载按钮。

本机服务由本次实施启动。关闭服务或电脑重启后，在 PowerShell 的项目目录运行：

```powershell
.\start-browser-bridge.ps1 --reuse-token
```

保持该窗口运行。在另一个终端查看状态：

```powershell
.\boss.ps1 browser status --probe
.\boss.ps1 browser tabs
```

## 状态的含义

- `connected`：扩展是否已连上本机服务。
- `authenticated`：是否观察到招聘端已登录页面；不是接口可用性的保证。
- `api_readable`：加 `--probe` 后，招聘职位接口是否成功返回。
- `account_error`：页面虽然像已登录，但账号接口不通或返回字段尚不能识别；此时停止业务请求，不凭昵称猜账号。

有多个已登录页面时，使用 `browser tabs` 返回的 target 显式选择：

```powershell
.\boss.ps1 --transport browser --browser-target "页面target" recruiter inbox --page 1 --json
```

未发现 BOSS 页面时运行 `browser open-login`。它优先复用已有页面，确实没有时才新建。扩展未连接时不会把当前 Chrome 判定为未登录。

## 只读核验命令

安装或更新扩展后，业务页面由 CLI 自动切换，不要求人工先点击“推荐牛人”或“沟通”。`cards` 自动进入推荐页面；`open-profile` 按当前卡片 ID 打开详情，不点击打招呼。自动导航、读取卡片、打开详情均已线上验证；当前推荐详情快照只取得经历概览，尚未取得完整简历正文。扩展重载后若未自动连接，需重启本机服务并在扩展点击“连接”恢复配对。

```powershell
.\boss.ps1 --transport browser browser cards
.\boss.ps1 --transport browser browser open-profile 候选人卡片ID
.\boss.ps1 --transport browser browser profile-snapshot
.\boss.ps1 --transport browser browser navigate chat
.\boss.ps1 --transport browser recruiter inbox --page 1 --json
.\boss.ps1 --transport browser recruiter resume-download 候选人ID --job 职位ID --security-id 上下文标识 -o sample.private.md
.\boss.ps1 --transport browser recruiter chat 会话ID --json
.\boss.ps1 --transport browser recruiter chat 会话ID --before 消息游标 --json
```

上述 ID 来自实际接口，不能用姓名代替，也不要把示例文字原样当作参数。

Markdown 保留接口返回字段及关联标识，不截断正文，但仍须与页面对照才能确认完整性。它不是 PDF 附件。输出文件已存在时会拒绝覆盖，请指定新文件名。

写操作只在服务启动时显式加 `--allow-writes` 才可用；当前实测服务没有开启。原版消息发送参数已实测报“缺少必要参数”，尚不可作为可用发送工具。发生超时或未知结果时先检查聊天记录，不能直接重复发送。

## 常见问题

- “连接失败”：确认本机服务正在运行、端口一致、令牌为本次服务显示的值。
- “页面已变化”：页面刷新或关闭后重新执行 `browser tabs`，不要继续使用旧 target。
- “账号标识缺失”：保存错误类型及返回字段结构供排查，不要粘贴 Cookie 或完整候选人资料。
- 使用原 Cookie 通道：在命令最前面指定 `--transport cookie`。它仍可能受当前 Windows 浏览器数据库权限或解密问题影响。

## 开发验证

```powershell
.venv\Scripts\python.exe -m pytest -m "not smoke" -q
node --test chrome-extension\tests\*.test.mjs
```

自动化测试使用合成数据，不代表已验证真实 BOSS 接口。线上记录必须单独记录。
