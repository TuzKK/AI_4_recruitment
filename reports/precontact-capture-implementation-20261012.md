# 联系前推荐简历截图实现记录

已实现：默认复用已有 Chrome 的扩展通道、按候选人 ID 开详情、固定展开/滚动、iframe边界校验、原始分段PNG、重叠可靠时长图、SHA256清单与核对报告。可选 debugger 权限由用户明确同意并在弹窗授予；本机桥接保持只读。每人刷新推荐页，存在残留详情或ID不可定位则停止，避免依据内容变化误归候选人。

本地验证：128项Python测试通过、7项线上smoke未运行；11项Node测试通过；新增文件Ruff通过。本地真实Chrome合成页面验证包含Canvas/iframe内部滚动与分段上限。测试数据为合成资料，不能作为BOSS线上截图证据。

真实采集尝试失败：扩展尚未连接。没有取得新的真实求职者截图，不能声明联系前完整截图可行。失败留证：[verification.md](../source/boss-cli-main/.runtime/precontact-capture/20261012-121326-935471/verification.md)。

启动与部署：[教程](../source/boss-cli-main/docs/precontact-capture.md)。新增入口：[脚本](../source/boss-cli-main/scripts/probe_recommend_capture.py)。结果保存在项目.runtime/precontact-capture/；候选人资料不进入公开报告。

待完成：重新加载0.2.0扩展并连接本机服务；真实1人采集与逐模块核对；扩展至5人；当前Chrome非活动标签兼容性验证。未实施OCR、模型评分或发送。
