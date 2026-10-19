# 牛人推荐联系前信息提取实测：2026-10-13

## 目标与方法

复用用户当前已登录的 Chrome 和只读本地连接器，不发送消息或发起联系。先采集推荐卡片及详情 DOM 文字，再临时观察打开同一候选人详情时浏览器实际收到的本站 JSON 响应。原始数据仅保存在 `.runtime`，本报告不含求职者个人资料。

## 真实结果

- 当前推荐页取得 14 张可见卡片；原始卡片保存在 [`cards.json`](../source/boss-cli-main/.runtime/recommend-text-probe/cards.json)。这证明卡片级自动采集可用，不代表取得完整简历。
- 同一候选人详情的推荐 iframe 页面文字约 6,418 字，但简历相关容器只有约 369 字；大部分页面文字属于推荐列表。`c-resume` iframe 的 DOM 文字为空。单人原始快照保存在 [`snapshot.private.json`](../source/boss-cli-main/.runtime/precontact-network/20261013-105145/snapshot.private.json)。
- 旧版只读 `/wapi/zpjob/view/geek/info` 对该卡片及岗位标识返回 `code=2`、未知的非法参数。网络诊断查明页面实际请求 `/wapi/zpjob/view/geek/info/v2`，HTTP 200、业务 `code=0`，响应体约 26 KB。
- v2 的 `geekDetailInfo` 为 `null`，`encryptGeekDetailInfo` 为约 24 KB 字符串；`hiddenResume=0`、`friend=false`。该字符串解码后的字节无常见纯文本或压缩文件头。这里仅能确认浏览器收到了加密详情，**不能将其当作已获得可读完整简历**。证据见 [`manifest.json`](../source/boss-cli-main/.runtime/precontact-network/20261013-105145/manifest.json) 与本地私有 [`network.private.json`](../source/boss-cli-main/.runtime/precontact-network/20261013-105145/network.private.json)。
- 用当前扩展对真实页面做两次最多 15 段的只读 Canvas 滚动探针，两次均为 `partial / resume_canvas_not_initialized`，保存 0 张正文段图。画布均停留在 300×150 初始化占位尺寸、无正文像素；第一次后页面仍确认登录。证据见 [第一次 Canvas 清单](../source/boss-cli-main/.runtime/precontact-canvas/20261013-105340-418970/manifest.json) 和 [第二次 Canvas 清单](../source/boss-cli-main/.runtime/precontact-canvas/20261013-110055-164455/manifest.json)。中间一次指定候选人的尝试因推荐列表刷新后该卡片消失而停止，未作为 Canvas 失败样本。

## 结论与下一步边界

现阶段已实现推荐卡片自动提取，以及同一候选人的页面文字和实际网络响应的本地留证；**联系前完整可读在线简历仍未实现或验收**。根因已缩小：页面使用 v2 加密详情并在无 DOM 正文的 `c-resume` 中渲染，直接读取 DOM 或调用旧接口都不能获得全文。当前真实 Canvas 探针也未形成可用的多段图。

扩展 0.2.14 增加了受限的只读网络诊断，复用原有 `debugger` 权限；本机服务已重启、扩展已重载。该诊断只用于定位数据来源，不能解密内容。下一阶段若继续追求全文，应先验证**浏览器页面已经解密后的数据能否从渲染状态导出**，并给验证设定终点；若只能获得像素，再评估分段图与 OCR。不要将 24 KB 密文、页面总字数或单张局部截图计作完整简历。

本地验证：扩展 Node 测试 19 项通过，桥接 Python 测试 12 项通过。`probe_recommend_network.py` 首次实测在写清单时因空 iframe 缺少 URL 抛错；原始采集已成功写入，后续已修复该清单生成错误，并从原始结果补写清单。未为此重复请求该候选人。
