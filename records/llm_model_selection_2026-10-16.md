# 招聘评分模型选型

记录日期：2026-10-16

- 名称：Qwen Plus，固定版本 `qwen-plus-2025-07-28`。
- 规格：阿里云托管文本模型，Plus 档；支持 100 万 Token 上下文；官方未公布本版本参数量，不能将其标为某个 B 参数模型。
- 调用方式：仅使用阿里云百炼 API，无需本地模型或服务器。使用非思考模式 `enable_thinking=false`。
- 选用原因：适合作为中文简历证据提取、招聘要求匹配及简短理由生成的评测基线；成本适中，固定快照便于比较评分规则迭代效果。粗筛、精筛先统一使用该模型，通过规则和阈值区分阶段。
- 参考价格：中国内地、输入不超过 128K Token 时，每百万输入 Token 0.8 元、非思考输出 Token 2 元；实际以账户地域及官方计费为准。
- 状态：本次完成选型；实际筛选质量需由本地样本的 API 评测确认。本记录不代表已修改应用默认模型或完成接口验证。

官方资料：https://help.aliyun.com/zh/model-studio/qwen-plus
官方价格：https://help.aliyun.com/zh/model-studio/model-pricing

## API verification update

2026-10-16：日期快照返回 HTTP 404 model_not_found，同一账户调用 `qwen-plus` 返回 HTTP 200。应用默认已切换为 `qwen-plus`，使用 `enable_thinking=false`。上面的快照规格与价格仅记录原选型，不能直接视为当前别名后端规格。

已完成120份本地样本的API评测与规则调优：最终放行二分类120/120，精筛三分类79/120。这是调优集结果，不能代表未知简历上的准确率。详见[评测记录](llm_screening_evaluation_2026-10-16.md)。
