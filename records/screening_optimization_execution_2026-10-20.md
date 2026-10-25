# 粗筛 / 精筛优化执行记录

## 范围与评测约定

- 仅调用阿里云 LLM API，不下载或运行本地模型。
- 原始语料：2,000 份简历、100 份岗位要求、10,000 个匹配对。
- 按简历隔离：训练 6,000 对、验证 2,000 对、最终测试 2,000 对；另有 20 个仅测试岗位。
- 原始“本体建模实施与交付工程师（伙伴）”招聘需求另对 400 份留出简历测试；120 份历史样本单独回归。
- 粗筛只见已保存的中文短简历；精筛见完整中文正文。离线诊断会评估所有精筛输入，实际流水线仅粗筛通过才进入精筛。
- 标签为 LLM 银标签，不代表人工金标准。300 对训练样本已独立盲审，其中 84 对三分类发生变化；修订冻结，不能据此宣称标签绝对正确。

## 优化目标

粗筛召回率 ≥90%、精确率 ≥70%；粗筛通过人群中的精筛精确率 ≥95%；整个流水线对 label=2 的召回率 ≥85%。
约束满足后以 `0.75 × 流水线召回率 + 0.25 × 最终精确率` 选择配置。
粗筛/精筛共享 0–100 量尺，候选阈值对为 45/70、50/75、55/80。
类别权重、未知项先验、证据覆盖率通过训练/验证集网格选择。不得使用测试结果反向调参。

## 已实现

1. `matching_eval/prepare_optimization.py`：数据哈希冻结、训练盲审、开发标签覆盖层、400 对本体测试标签。
2. `matching_eval/optimize_screening.py`：分阶段证据缓存、配置网格、宏平均/分岗位指标、冻结配置、测试开启身份验证、成功结果账本与完成封印。
3. `recruitment_app/generic_scoring.py`：可配置通用评分权重、未知先验与阶段覆盖率；旧默认行为保留。
4. `matching_eval/screening_prompt_variants.py`：固定 `evidence-v1`，通过原文片段编号恢复真实引用，避免单行简历产生虚构行号；岗位准入条件不把“经验不限”当作硬要求。
5. 保护测试覆盖配置校验、流水线漏召回计数、文件篡改、冻结后代码修改、旧标签复用新实现等情形。

## 首轮发现

- 基线 600 对训练试点共 1,200 次阶段抽取，首轮 1,128 成功、72 失败；成功项已缓存，失败项正在补跑。尚不能报告全量分类准确率。
- 岗位引用失败源于模型拼接不连续句子；格式纠正会列出具体错误引用，不放宽原文校验。
- 单行长简历容易产生不存在的行号；新版本采用分句片段编号。
- 历史 R002 的原 PDF 文字层只有水印。使用云端视觉模型恢复正文，保留原 PDF 与转录来源哈希；不把资料读取失败计为真实负样本。
- 可用视觉模型通过当前凭据的 `/models` 查询确认，转录使用 `qwen3-vl-plus`。普通评分仍为 `qwen-plus`。
- 图像接口依据：[阿里云 OpenAI 兼容接口文档](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions)。
- PDF 渲染只安装 `pymupdf==1.26.4 --no-deps`；无本地推理模型。

## 迭代决策

- `evidence-v1` 试点 1,195/1,200 次抽取成功，5 次需复核。训练误差显示部分岗位引用过长，多个能力项被整段要求覆盖；停止全量扩展，保留缓存与失败记录。
- `evidence-v2` 将岗位引用细化至分句，并对内部字段 ID 做确定性编号，避免过长或重复字段名。该模块保持独立且不可变。
- `evidence-v3` 继承 v2 岗位规则，并为缺少标点的简历增加最多 180 字符的原文片段边界；跨片段引用仍恢复原文连续区间。复用 v2 岗位缓存前检查 v2 实现身份，简历证据另行缓存。
- 全量候选比较为 baseline 与 evidence-v3。v1/v2 的停止决定只基于训练数据，不使用最终测试集。
- 120 份历史摘要已完成。N006、S090 的自由改写反复不符合长度且出现事实漂移，因此改为 LLM 选择原文片段、本地按原文拼接；不补造事实。
- 评分相关测试 28 项通过；独立只读代码复核未发现最终测试隔离、v3/v2 缓存复用或原文片段还原的阻断问题。
- 离线失败样本仍留在分母，标注 `technical_review_required`；任何技术失败都会阻止“达标”判定。最终评测要求全部证据成功校验，不允许降级占位。
- Top-K 仅在通过粗筛的人群中计算；新增 `coarse_high_fit_yield`，用于诊断机会利用率，不能替代线上日常效果保证。

## 发布条件与当前状态

当前因阿里云账户欠费中断，未开启最终测试，未切换应用默认评分机制，未执行 BOSS 打招呼。
只有独立测试和本体测试均达标、历史回归无退化时才切换默认配置。否则保存报告并保留旧默认。
最终结果以 `Samples_for_optimization/generic_2000/optimization/` 下冻结配置、进度与完成封印为准。

### 账户阻塞与断点

阿里云兼容接口实际返回 HTTP 400：

```json
{"error":{"code":"Arrearage","type":"Arrearage","message":"Access denied, please make sure your account is in good standing."}}
```

这不是模型名错误或评分代码异常。已停止当前全部评分请求，不能宣称全量优化或最终验收完成。

| 版本 | 已缓存且通过校验的阶段结果 | 计划阶段结果 | 剩余 |
|---|---:|---:|---:|
| baseline | 11,844 | 16,000 | 4,156 |
| evidence-v3 | 9,821 | 16,000 | 6,179 |

数量由全部开发集匹配对的实际缓存文件重新统计；比最后一条进度日志更准确。
运行状态保存于 `optimization/execution_status.json`。
新增加 `api_guard.py`：收到 Arrearage 后停止该进程后续调用，取消队列，不把欠费当普通格式错误无限重试。
评分与评测相关测试共 31 项通过；这些是代码测试，不是简历分类准确率。

账户恢复后，复用现有缓存续跑：

```powershell
$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY', 'User')
$env:PYTHONIOENCODING = 'utf-8'
.\source\boss-cli-main\.venv\Scripts\python.exe -m matching_eval.optimize_screening development --workers 96
.\source\boss-cli-main\.venv\Scripts\python.exe -m matching_eval.optimize_screening development --prompt-tag evidence-v3 --workers 96
```

两组完成后，先检查剩余技术失败并补跑，再用最新实现重新汇总。网格计算已经增加一次校验、多组重算的缓存，保持与完整评分函数相同结果。
**以下是后续步骤说明，不应在开发评测仍缺失结果时运行。**

```powershell
.\source\boss-cli-main\.venv\Scripts\python.exe -m matching_eval.optimize_screening aggregate
.\source\boss-cli-main\.venv\Scripts\python.exe -m matching_eval.optimize_screening aggregate --prompt-tag evidence-v3
.\source\boss-cli-main\.venv\Scripts\python.exe -m matching_eval.optimize_screening freeze --tags baseline,evidence-v3
.\source\boss-cli-main\.venv\Scripts\python.exe -m matching_eval.optimize_screening final-test --workers 96
.\source\boss-cli-main\.venv\Scripts\python.exe -m matching_eval.write_optimization_report
```

最终测试开封后只能在原冻结身份下补跑技术失败，不能改代码或配置后重新测同一批留出数据。
