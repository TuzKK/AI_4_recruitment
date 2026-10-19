# 推荐在线简历截图验证

## 2026-10-13 文字与网络响应探针

当前推荐详情的 DOM 只返回简历概览，`c-resume` iframe 没有可读正文。已登录 Chrome 的实际详情请求为 `/wapi/zpjob/view/geek/info/v2`；该响应中的 `geekDetailInfo` 为 `null`，正文位于 `encryptGeekDetailInfo`。该字段是密文，不能直接作为可读简历。真实试验见 [报告](../../../reports/precontact-text-network-live-20261013.md)。

扩展 0.2.14 提供受限的只读网络诊断，运行 `scripts/probe_recommend_network.py` 会刷新推荐页、选择当前第一张卡片、打开详情，并将卡片、页面快照和本站 JSON 响应保存在 `.runtime/precontact-network/`。需要现有登录和已连接扩展；运行前设置与 `boss.ps1` 相同的 `BOSS_BRIDGE_FILE` 和 `BOSS_TRANSPORT=browser`。输出包含真实个人资料，只用于本机核对，状态默认 `unverified`。这不是全文简历导出工具。

扩展 0.2.15 增加了只在推荐和 `c-resume` iframe 的页面主环境、`document_start` 时运行的观察脚本。它记录页面自己解析出的结构化简历对象或实际画到 Canvas 的文字，并随 `profile-snapshot` 一起返回；不调用解密接口。代码和合成测试已完成，**真实 Chrome 尚未重载到该版本并验证**。若 `resumeTap` 为 `null`，先核对扩展是否重载和页面是否重新导航，不能据此判断页面没有解密后数据。

此工具是只读可行性验证，默认复用当前 Chrome 登录页面。无需重启 Chrome、导出 Cookie 或安装另一个招聘平台。首次更新/连接扩展属于部署操作，之后详情打开、展开、滚动和截图由脚本调度。每人采集前自动刷新固定推荐页，重新按 ID 定位，避免上一人详情残留；刷新后对象不可见则停止并留证。

## 当前 Chrome 连接

1. 在 chrome://extensions 中重新加载项目已有的“BOSS CLI 本地连接器”。目录为 chrome-extension，版本 0.2.13。若尚未安装，只从本项目加载该目录。
2. 本机服务保持只读，启动命令为 start-browser-bridge.ps1 --reuse-token；这次服务已以隐藏进程启动，配对信息在 .runtime/capture-bridge.log，关闭浏览器不会自动停止服务。
3. 在扩展弹窗填入端口 17891 和该日志里的配对令牌，然后点击“连接”。不要将令牌粘贴到聊天或报告。
4. 仅在明确同意扩展增加 debugger 权限后，在 chrome://extensions 重新加载，若 Chrome 要求确认新增调试权限则确认；弹窗点击“检查截图权限”，应显示“截图权限可用”。debugger 不能通过可选权限按钮申请。该浏览器权限较广；本项目只提供固定推荐详情截图/滚动操作，不能从 CLI 提交任意 JavaScript 或调试命令。Chrome 可能显示正在调试的提示。

## 执行

在项目目录 PowerShell 运行：

~~~powershell
$env:PYTHONUTF8 = '1'
$env:BOSS_BRIDGE_FILE = Join-Path $PWD '.runtime\browser-bridge.json'
.\boss.ps1 browser status --probe
.\.venv\Scripts\python.exe scripts\probe_recommend_capture.py --limit 1
~~~

指定当前推荐中的对象：--candidate-id ID。扩大样本：--limit 5。存在多个登录页面时，用 browser tabs 返回的 target 配合 --browser-target。--output 指向新的目录，已有目录拒绝覆盖；每人默认 120 秒、100 段上限，可用 --max-seconds / --max-segments 调整。

使用 capture 可选依赖安装 Pillow/Playwright：uv pip install --python .venv/Scripts/python.exe -e ".[capture]"。已有 Chrome 模式截图由扩展负责，不依赖 Playwright 启动新浏览器；Pillow用于可靠重叠校验和长图拼接。

结果默认保存 .runtime/precontact-capture/时间/：每人 segment-NNN.png、可能的 resume-long.png、detail-text.private.txt、manifest.json，以及总 manifest.json 和 verification.md。目录已被 gitignore 排除，包含候选人资料，不作为公开示例。

## 核对与限制

- captured_unverified 只表示到达稳定底部，人工完整性核对仍待完成。检查对象、个人介绍、工作、项目、教育、技能等实际可见模块及最底部内容。
- partial 表示时限/分段上限、布局变化或错误；原图和原因保留。拼接匹配不可靠时不生成长图，使用原始分段图核对。
- 继续沟通/已沟通标记可说明已有联系；没有标记只能记 unknown，不能宣称未联系。采集前后联系状态核对单列。
- 不点击打招呼、联系、分享或发送；展开操作只匹配普通“查看全部/展开”入口。账号/文档变化或验证码停止，错误不自动重放。
- 此模式不抢占桌面鼠标或主动切换活动标签，但会操作所选 BOSS 标签；采集期间不要在同一标签手动切换候选人。
- 当前账号未展示的内容无法靠截图取得。截图成功不等于网页全量内容已核实。
- 本轮不执行 OCR/模型评分；原始图验收后再接 OCR。
- 保留独立浏览器实验入口 --independent，仅用于对照测试。首次登录加 --login；对照模式选 --headed 或 --headless；默认使用独立 profile，不复用日常数据目录。

## 本地测试

~~~powershell
$env:BOSS_BRIDGE_FILE = Join-Path $PWD '.runtime\nonexistent-test-bridge.json'
.\.venv\Scripts\python.exe -m pytest -m "not smoke" -q -p no:cacheprovider
node --test chrome-extension/tests/*.test.mjs
~~~

真实平台截图与本地合成 Canvas 测试分开验收，不能以本地测试通过声明 BOSS 线上已可用。

## 0.2.6 实测驱动改进

推荐详情外层容器实测可读滚动高度4344px、可见高度890px。截图请求改用 captureBeyondViewport，范围受实际页面内容和iframe祖先边界约束，而非仅桌面可见视口；实际Chrome合成测试确认窗口外的底部像素能保留。真实BOSS滚动全覆盖仍待本版实测，不因本地测试通过宣布完整。

外层滚动后若内层iframe还有未覆盖独立滚动范围，保留诊断图并标partial。普通DOM无iframe时恢复回退。被裁剪的诊断图只保存一次并停止。

## 0.2.7 当前优化

首次渲染图保存在diagnostic-NNN.png，重新发现初始化后的实际滚动容器。若视口只在底部裁掉不超过64px，且存在已验证的长滚动容器，程序临时缩短该容器至可截图范围；结束时恢复原始内联样式并记录viewport_restored。不会调整Chrome窗口或登录状态。

临时调整前，扩展会在该容器记录原始样式。即使调整后的返回消息丢失，也会尝试立即恢复；若扩展后台中断，下次准备截图时会恢复遗留样式。恢复失败时清单标为partial，原因是viewport_restore_failed或viewport_restore_unverified。

只有稳定、未裁剪的segment-NNN.png计入覆盖；跨段宽高/总高度变化、出现缺口、未从顶部开始或滚动未前进都会停止为partial。运行期间请勿在同一BOSS标签手动切换候选人。

外部Chrome控制器验证命令：node scripts/check_capture_controller.mjs。该测试仅使用合成页面，不连接日常Chrome；已验证固定高度裁剪、自动适配、5段滚动到底及原样恢复。真实BOSS全覆盖仍需0.2.7线上验收，介绍等Canvas内的展开控制仍需单独核实。

## 0.2.8 真实超时后的调整

真实 BOSS 的长 Canvas 详情连续两次在正式截图时触发 Page.captureScreenshot 超时。控制器现只请求根视口内可见像素；底边少量超出视口时先保存诊断图，再将已经确认的外层滚动容器临时缩高后正式采集。长内容仍按滚动分段覆盖。当前只是本地合成页通过，真实长图需以 0.2.8 实测的分段清单和人工核对为准。

## 0.2.9 后台渲染诊断

0.2.8 已限制截图在浏览器视口内，真实页仍在正式长内容截图时超时。0.2.9 截图期间仅对目标标签启用 Chrome 的焦点模拟，结束立即关闭；不切换活动标签，并在截图元数据记录目标标签当时是否处于活动状态。合成 Chrome 的 5 段截图尺寸均为 500×560px，临时样式恢复通过。真实效果仍待验证。

## 0.2.10 只读 Canvas 导出验证

真实 BOSS 页在 0.2.9 连第一张调试截图都发生 Page.captureScreenshot 超时，因此撤销焦点模拟实验。新增独立的固定操作 resume_canvas：仅在当前推荐页按同一候选人 ID 打开详情后，识别唯一的 c-resume 文档；先返回 Canvas 页数、位置和尺寸，再按 0..29 的单页索引导出已渲染 PNG。不会接受任意 JavaScript、CDP 命令或其他页面地址。本机服务保持 allow_writes=false。

运行：.\.venv\Scripts\python.exe scripts\probe_recommend_canvas.py。输出位于 .runtime/precontact-canvas/时间/，包含逐页图片、清单和核对说明；状态 canvas_pages_unverified 仅表示列出的画布均已导出，仍需核对是否包含全部展开后的在线简历。隔离 Chrome 验证了两张模拟画布的尺寸、不同内容和 PNG 编码；真实 BOSS 页数与可导出性待验收。

## 0.2.11 占位画布和验证页保护

实测 0.2.10 的 c-resume 初始 Canvas 为 300×150，即使 toDataURL 成功也只是空白占位。该次本地清单已降为 partial 并改为诊断图。当前扩展仅在 Canvas 至少 400×400 且可见时视为已初始化；页面内最多等待 15 秒，CLI 最多进行两次检查。浏览器若进入 verification_required，先在原 Chrome 页面人工完成 BOSS 验证，再继续运行；程序不会尝试绕过验证。

## 0.2.13 外层滚动 Canvas 分段探针

0.2.12 已在真实推荐页自动导出一张 1044×1734 的正文 Canvas，但它只覆盖约 867 CSS px 的可见区域。此前同一类详情的外层可滚动高度约 4344px，因此单张图不能算完整简历。使用 `--scroll` 开启新探针：

~~~powershell
$env:PYTHONUTF8 = '1'
$env:BOSS_BRIDGE_FILE = Join-Path $PWD '.runtime\browser-bridge.json'
.\.venv\Scripts\python.exe scripts\probe_recommend_canvas.py --scroll --max-pages 15
~~~

探针在每个滚动位置导出一张 Canvas，先验证最顶部画布与当前已打开对象相同，导出后恢复顶部并再次验证。外层滚动高度变化、Canvas 文档变化、画面不变、相邻段像素不连续或底部未覆盖时标记 `partial`，保留原图供核对。只有连续性和几何覆盖通过才生成白底 `resume-long.png`；即便生成，状态 `canvas_segments_unverified` 仍需要人工检查候选人身份、正文模块、展开状态和底部。`--max-pages` 在滚动模式表示最大分段数。当前版本的真实连续滚动效果尚待重新加载扩展后验证。
