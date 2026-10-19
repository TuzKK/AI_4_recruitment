# Windows：接入已经登录的 Chrome

本次适配参考最早的 `boss-resume-filter`：发现 Chrome 调试端口后通过 CDP 复用现有页面。普通启动的 Chrome 没有 CDP 端口，不能用相同方式直接连接，因此补充本地扩展接入。此方式无需重启 Chrome、重新登录或复制 Cookie。

## 已登录、没有调试端口的 Chrome（当前推荐）

1. 保持现有 BOSS 招聘者页面打开。在原 Chrome 新标签页打开 `chrome://extensions`，打开右上角“开发者模式”，点击“加载已解压的扩展程序”。
2. 选择项目中的 `chrome-extension` 文件夹（不是父目录）。
3. 打开本机程序 `http://127.0.0.1:8000/settings`，点击“首次接入：获取扩展配对信息”，复制配对码。
4. 在 Chrome 扩展菜单里点击“BOSS 本地招聘连接器”，粘贴配对码，点击“连接本机招聘程序”。
5. 返回本机设置页，点击“检测已打开的 Chrome”。确认目标页面显示“已登录招聘者账号”，点击“接入此页面”。
6. 创建招聘任务时选择该账号。保持该 BOSS 标签页打开并处于牛人推荐页。

只需加载扩展一次。程序重启后扩展会尝试重连；浏览器重启、页面刷新或跨文档跳转后，需重新检测并绑定当前页面。未完成扩展配对时，仅能检测 Chrome 进程，不能声称已确认登录。

扩展安装由用户在 Chrome 中完成；程序不静默安装扩展，不新建或重启 Chrome。连接、配对、检测均不发消息，只有显式启动招聘任务才执行任务动作。

## 已开启调试端口的 Chrome

直接点击“检测已打开的 Chrome”。支持 Windows 进程中发现的调试端口、项目专用配置目录记录的端口，以及手工输入的本机端口。仅支持 `http://127.0.0.1:<port>` 或 localhost，不接受远程服务器。

Chrome 136 起，调试默认用户目录的限制变更，不能把 `--remote-debugging-port` 当作任意现有窗口的接管开关。官方说明：https://developer.chrome.com/blog/remote-debugging-port

## 功能边界

- 推荐卡片读取 → 岗位匹配初筛 → 达标后打招呼，任务绑定所选账号。
- 登录识别检查招聘页面 DOM 及 iframe，URL 本身不算已登录。
- 页面刷新、退出登录、验证弹窗、标签页关闭、连接断开等情况会停止或拒绝任务。
- 打招呼只点击一次；未确认结果则报错停止，不自动重复发送。
- 停止任务会等待已经开始的操作退出；评分返回后和发送前均检查停止标记。
- 浏览器模式原有聊天回复、附件收集函数未实现，界面和任务日志明确说明。此适配不等于完整在线简历抓取。
- Windows 浏览器模式不沿用原 macOS 流程硬编码的“合肥+汽车行业”过滤；按任务岗位初筛及阈值处理。
- 删除账号只删除本机绑定，不关闭 Chrome，不删除浏览器登录数据。

## 扩展与本机服务

Manifest V3，Chrome 116+。权限仅限 scripting、storage、alarms、BOSS 网站和本机 8000 端口。不读取 Cookie，不申请 debugger 权限，不使用任意脚本执行接口。执行脚本随扩展本地打包；协议操作固定为 discover、inspect、cards、greet、scroll。

配对码保存在 `backend/data/browser_bridge_token`，不入版本控制，通过 WebSocket 首条消息传递，不出现在 URL。扩展后台每 20 秒心跳，参考官方示例：https://developer.chrome.com/docs/extensions/how-to/web-platform/websockets

## 启动与验证

当前机器已经安装依赖。运行根目录 `start-windows.cmd`，或 `backend/.venv/Scripts/python.exe main.py serve --host 127.0.0.1 --port 8000`（工作目录 backend）。启动脚本只启动服务，不打开浏览器。

测试：

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd ..
node --test chrome-extension/tests/worker.test.mjs
npm.cmd --prefix frontend run build
```

Python DOM 测试使用隔离的无界面 Chrome 和本地模拟页面；扩展后台测试使用模拟 Chrome API，不触碰真实 BOSS 或发送消息。尚未由用户加载扩展时，真实账号接入仍待完成，不能以模拟测试代替实际登录验证。

## 手动网页聊天

新增 `/chat` 页面：选择插件接入账号 → 在 BOSS 中打开已有会话 → 读取当前会话 → 输入文字 → 点击发送。
这是独立的人工触发入口，不会自动加入招聘任务，也不生成或发送 LLM 话术。

- 扩展更新后需在 `chrome://extensions` 重新加载并连接，然后在系统设置重新接入原聊天标签页。
- 发送前要求选中联系人和聊天面板的身份一致；无法识别时停止。
- 已有文字或图片草稿不会覆盖。每个预览仅允许一次发送尝试。
- 超时、断线或无法确认消息时记为 `unknown`，不自动重发。页面出现消息也不代表送达或已读。
- 本地发送记录独立保存在 `browser_chat_sends` 表，不是 BOSS 历史消息同步。
- 测试使用隔离 Chrome 与模拟会话，没有向真实联系人发送消息。
- 已在当前 BOSS 聊天页验证只读会话预览，识别了联系人、组件标识和编辑器。真实消息发送尚未执行验证；页面改版时可能需要调整适配器。
