# 简历岗位匹配：开源组件复用与评估状态

## 选型与可复用性

- 专项参考项目：[Recruiter Pro](https://github.com/Sharawey74/Recruiter-Pro)，本地固定提交 `daf160bbe97e269846a78e53b5c6f5d2affeb0bf`，MIT 许可。源码位于 `source/Recruiter-Pro-daf160bbe97e269846a78e53b5c6f5d2affeb0bf`。
- 复用 `SkillMatcher` 与技能别名词表：技能归一化、必需/优先技能区分、整词匹配和缺口计算；保留原始许可及出处。补充本体、知识图谱、数据治理、数仓等中文别名。
- 不复用其固定岗位权重、英文简历解析、额外 ML 模型和整套 Web 应用。当前项目按招聘需求动态生成标准，Qwen API 抽取与岗位相关的语义证据，规则层依据可核验原文算分与执行硬条件。
- 该仓库具备独立组件和测试，但缺乏足够的公开生产使用证据，不能仅凭项目自述称其已获生产级稳定性验证。已针对移植的匹配行为做本项目测试；尚未在当前环境运行上游完整测试套件。

## 已嵌入的评分

`recruitment_app/shadow_matching.py` 对同一份 Qwen 证据计算影子评分：

1. Qwen 根据招聘要求对候选人原文逐项给出 `0/1/2` 级别与原文引文，代码核实引文确在原文，并按岗位权重计算证据分。
2. 开源词表和本地中文别名做确定性技能匹配，区分必须与优先技能，并防止 Java 与 JavaScript 一类子串误命中。
3. 有可识别技能时影子分采用 `75% × LLM 证据分 + 25% × 技能匹配分`；无可识别技能时只用证据分。硬条件、资料不完整及证据异常仍阻止自动通过。

当前 `shadow_coarse`、`shadow_fine` 只记录结果。现有分数继续控制联系，不会把未经评估的新阈值用于 BOSS 打招呼。整个评分仅依赖已配置的 DashScope Qwen API 和轻量确定性规则；不部署、不下载、不运行本地模型。

## 数据与验证边界

- 原有 8 份完整 PDF：人工高匹配 2 份，人工拒绝 6 份；清单和 SHA256 保存在私有 `Samples_for_optimization/manifest.json`。
- 外部负例：从 Apache 2.0 的 [SyntheticResumeData](https://github.com/jijunhao/SyntheticResumeData) 提交 `3ecd09129f65955e743aacf67f2785fcee10d461` 选取 10 份不同职业的合成中文简历，仅导出工作与教育内容；清单和 SHA256 在 `Samples_for_optimization/external_negative/manifest.json`。这组数据只反映明显不相关职业的误报，和真实样本分开统计。
- 本地已核验 18 份样本均可读取，规则组件在这 10 份外部负例中没有误识别本岗位列举的 SQL、Python、JavaScript、本体、知识图谱、数据治理技能。
- 对比脚本 `recruitment_app/benchmark.py` 使用同一次 Qwen API 证据，分别输出旧评分与影子评分的真实样本精确率、召回率和 `0.75 × 召回率 + 0.25 × 精确率`；外部负例仅单列误报数。运行 `recruitment_app/benchmark.ps1` 可生成本机报告。
- 当前执行环境没有 `DASHSCOPE_API_KEY`，因此尚无 Qwen 实测分数和阈值结论，不能宣称指标已有提升。现有 8 份样本均为完整简历，没有联系前快照，不能测粗筛召回或验证每日打招呼后高匹配比例达到 10%。
