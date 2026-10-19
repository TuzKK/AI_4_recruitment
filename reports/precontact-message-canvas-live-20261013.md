# 牛人推荐在线简历：页面消息与画布实测

日期：2026-10-13。范围：复用当前已登录 Chrome，只打开推荐卡片详情，未执行打招呼、联系或发送操作。候选人原文及截图仅保存在 `source/boss-cli-main/.runtime/`，本报告不记录个人信息。

## 本轮实现

- `BOSS CLI 本地连接器` 0.2.16 在推荐 iframe 被动记录来自同源 `c-resume` 子 iframe 的 `IFRAME_DONE`、`WASM_ERROR`、`WASM_INIT_ERROR`、`WASM_NO_SUPPORT` 消息；校验消息来源，不改变页面消息或调用额外接口。
- 本地探针保存卡片、页面快照和同源网络响应，并在公开清单中只列消息类型及字段名。与当前卡片 ID 匹配的可读字段现自动另存为 `abstract.private.json` 和 `abstract.private.md`；如 `geekDetailInfo` 为空，状态为 `partial / abstract_only`。
- 扩展 25 项测试及 Python 142 项测试通过；目标扩展 ID `alggalljiolpnnnnopmcpemmmjgobhgj` 已重新加载并连接，真实页面确认观察脚本注入推荐和简历 iframe。

## 真实结果

| 证据 | 第一位 | 第二位 |
| --- | --- | --- |
| 本地目录 | `.runtime/precontact-network/20261013-035158/` | `.runtime/precontact-network/20261013-035948/` |
| `IFRAME_DONE` | 收到，身份匹配 | 收到，身份匹配 |
| 可读概览 | 工作 3 条、教育 1 条；无项目条目 | 工作 3 条、教育 1 条；无项目条目 |
| `geekDetailInfo` | `null` | `null` |
| 在线简历 Canvas 复查 | 最终 300×150 空白占位 | 300×150 空白占位 |

另外两张不同卡片的对照目录为 `.runtime/precontact-network/20261013-040505/` 和 `20261013-040520/`，均收到身份匹配的 `IFRAME_DONE`，`geekDetailInfo` 仍为 `null`。第五张卡片使用修改后的探针自动导出摘要，目录 `.runtime/precontact-network/20261013-040810/`；清单显示 `partial / abstract_only`，包含工作 2 条、项目 2 条、教育 1 条，两个摘要文件已生成。其 Canvas 复查同样是 300×150 空白占位。

第一位的 `/wapi/zpjob/view/geek/info/v2` 响应为 HTTP 200、业务码 0，`encryptGeekDetailInfo` 长度 19,992 字符，`geekDetailInfo` 仍为 `null`。公开前端脚本 `https://static.zhipin.com/zhipin-boss/wasm-resume-container/v230/assets/index-UWhPserd.js` 显示页面会将加密正文交给 WASM 渲染，并在 `IFRAME_DONE` 中带回摘要。实测完成消息并未带回解密后的正文，因此不能把可读概览或密文认作完整简历。

第一位曾在打开详情后出现一次 1044×1782、含非空像素的画布，但稳定校验未通过，也未导出为图片；刷新后回到空白占位。先前版本另有一张已保存的 1044×1734 正文局部画布：`.runtime/precontact-canvas/20261012-185612-691654/canvas-000.png`。它只覆盖局部可见区域，底部未核实。当前滚动探针输出 `.runtime/precontact-canvas/20261013-115507-182983/`，状态为 `partial`，原因 `resume_canvas_not_initialized`，仅保存了占位诊断图。

## 结论与后续判据

目前已自动取得推荐卡片和身份匹配的可读经历概览；**未取得本轮五位候选人的完整联系前在线简历**。0.2.16 的消息监听证明扩展连接、页面脚本和完成消息均可用，但完成消息本身只含摘要。是否能自动取得完整正文，取决于页面是否实际稳定绘制完整简历、以及滚动到底部后是否仍有可核对内容。只有保存每段正文、验证相邻段连续、确认底部和候选人身份，才可升级为“完整”；不能仅凭 `IFRAME_DONE` 或单张局部图升级状态。

下一步优先针对画布偶发绘制做只读诊断与导出，复用当前 0.2.16，无需继续盲目更新扩展。若页面持续仅显示概览和占位画布，则当前账号在该详情下没有可核实的完整正文，程序应停在 `partial`，不推测解密内容。
