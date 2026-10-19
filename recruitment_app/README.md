# 单页招聘筛选应用

2026-10-19：新增通用评分`generic-v1`的受控测试接口，统一两阶段分数并显示证据覆盖率。尚未完成跨岗位语料评测，网页默认仍为旧规则；不能把下面的旧评分结果视为新机制结果。见[实际进度](../records/generic_scoring_progress_2026-10-19.md)。

应用目录独立于 `source/Boss-main` 和 `matching_eval`。打开本地网页，填写完整招聘需求、打招呼人数上限及首条消息后开始。LLM 按本次岗位生成评分标准；每人先粗筛，再用联系前完整资料独立精筛。只对精筛通过者执行打招呼和消息发送。

## 首条消息模式

在“精筛通过后的消息方式”选择：

- **固定消息**（默认）：发送自己填写的模板，支持`{职位名称}`替换，不额外调用消息LLM。
- **AI问候与提问**：Qwen Plus非思考模式根据完整招聘需求和已核验简历生成80—120个非空白字符的单段消息，包含问候与1—2个岗位相关问题，再由另一次独立Qwen Plus调用复核。

消息只有通过程序检查和LLM复核后，才开始打招呼并发送审核原文。内容不合格时重写一次，再失败就跳过该人；API异常时暂停任务，恢复后可继续审核已保存草稿。筛选未通过者不会生成消息。两种模式共用原有联系人数上限。

网页候选人表显示消息内容、复核状态与联系状态/原因；任务文件保存生成/复核模型、提示词版本、尝试记录及正文摘要。已生成消息可能包含简历经历片段，完整简历不额外落盘。发送结果不明时仍需人工核查，不会自动重发。

旧任务未设置`message_mode`时按固定消息执行。新建任务可传`message_mode: "fixed" | "llm"`，AI模式可省略`message`。切换表单只影响新任务，不修改正在运行或恢复中的任务。更新代码后需重启本地网页服务并刷新页面。

模型选择、API样例与验证结果见[消息生成与复核记录](../records/llm_outreach_implementation_2026-10-16.md)。

## 当前评分与早期影子方案

新评分借鉴 MIT 授权的 [Recruiter Pro](https://github.com/Sharawey74/Recruiter-Pro) 技能词表与整词匹配组件，结合 Qwen API 对岗位要求和候选人原文进行语义证据提取、硬条件核对。Qwen 的证据级别占 75%，可识别技能的规则匹配占 25%；没有可识别技能时仅使用证据分。粗筛提示词认可有事实支撑的可迁移经验，精筛要求具体工作与交付证据。开源来源及不复用部分见 `_vendor/recruiter_pro/SOURCE.md`。

上述为早期影子方案，保留用于历史对比。当前正式流程的 `coarse`、`fine` 已接入与本地评测相同的细化评分和能力门槛，详细规则见下文；详细评分不再叠加旧影子分数。用户要求的召回率75%/精确度25%用于评测指标，不等于模型与规则的混合权重。全程只调用 DashScope LLM API，不下载或运行本地模型，也不需要部署服务器。

## 首次准备

1. 在本机环境中设置 `DASHSCOPE_API_KEY`；可选设置 `MATCHING_BASE_URL` 为该密钥对应地域的 DashScope HTTPS 兼容接口。简历文本会发往该模型服务。
2. 在 Chrome 中登录 BOSS 招聘者账号，重新加载 `source/boss-cli-main/chrome-extension`，并连接已有本地连接器。关闭先前的只读桥接服务，在 `source/boss-cli-main` 运行 `./start-browser-bridge.ps1 --reuse-token --allow-writes`。不要在其他会话展示配对令牌。
3. 从工作区根目录运行 `./recruitment_app/run.ps1`，打开 `http://127.0.0.1:8765/`。本地页面只绑定 `127.0.0.1`。

模型和 BOSS 服务的实时可用性需在实际账号环境核查。启动页面本身不会发送消息；点击“开始筛选”才授权本次上限内的联系动作。登录失效、验证、账号变化及发送结果不明时不会自动重复发送。

## 联系前完整简历接口

当前交接文档只验证了推荐卡片和部分可读经历摘要，**尚未验证未联系候选人的完整在线简历可稳定取得**。所以当前真实运行可完成采集与粗筛，但若连接器没有提供经核验的全文，将把该人记为 `insufficient_resume`，不会打招呼。模拟全流程测试不能代替真实 BOSS 验收。

接入另一终端的信息提取成果时，`profile_snapshot` 必须在顶层提供：

```json
{
  "full_resume": {
    "candidate_id": "与推荐卡片 geek_id 完全一致",
    "coverage": "complete",
    "verified": true,
    "sections_complete": true,
    "source": "precontact_verified",
    "text": "核对过工作、项目、教育等模块及页面终点的完整正文"
  }
}
```

上述字段只有逐人核对成功才可标 `complete`。任何缺失、身份不一致或超过 30,000 字符的正文都暂缓联系；不会把密文、概览或截断文本当全文。若另一终端采用不同输出结构，只调整 `recruitment_app/boss.py` 的适配层，不更改其采集代码。

## 结果与复核

运行记录保存在 `.runtime/runs/<运行 ID>.json`，包含岗位标准、评分证据和状态；候选人正文不复制到运行记录。`results/<职位名称>_YYYY-MM-DD/qualified_contacted.txt` 只包含两次发送均核实成功的人员，每人之间空一行；同日按候选人 ID 去重。目录在 `.runtime` 下，仅留本机。

应用根据候选人 ID 而非姓名关联会话。`needs_review` 表示动作结果不明，恢复任务时不会自动重发。页面有“暂停”和“恢复上次任务”。

人工复核后，可准备 `{候选人 ID: "high_match" 或 "rejected"}` 的 JSON 标签，并运行：

```powershell
& 'source/boss-cli-main/.venv/Scripts/python.exe' -m recruitment_app metrics 'recruitment_app/.runtime/runs/<运行 ID>.json' labels.json
```

报告分别计算粗筛和精筛的召回率、精确度以及 `0.75 × 召回率 + 0.25 × 精确度`；数据或标签不完整时不报告加权结果。每日打招呼后人工确认的高匹配比例以真正核实过打招呼的人为分母，目标为至少 10%，不能由现有 8 份完整简历样本保证。

跨本日所有运行统计实际打招呼人数和人工确认的高匹配比例：

```powershell
& 'source/boss-cli-main/.venv/Scripts/python.exe' -m recruitment_app daily-yield 2026-10-13 labels.json
```

测试：

```powershell
& 'source/boss-cli-main/.venv/Scripts/python.exe' -m pytest recruitment_app/tests -q -p no:cacheprovider
node --test recruitment_app/tests/greet.test.mjs
```

## 本地 120 份样本两层评测

网页底部现有“本地样本评测”：先点“载入测试岗位”，再点“评测本地样本”。它只使用 `DASHSCOPE_API_KEY` 调用阿里云 Qwen，不连接 BOSS，也不发送打招呼或消息。页面仅展示粗筛通过者的精筛分数、匹配理由和关键缺口；完整报告可从页面下载。粗筛卡片是从正文选取技术证据的至多 200 字代理输入，不是 BOSS 真正的联系前资料。

也可在已设置 API Key 的 PowerShell 终端运行：

```powershell
& source/boss-cli-main/.venv/Scripts/python.exe -m recruitment_app.local_eval --output recruitment_app/.runtime/local_evals/baseline.json
```

报告覆盖 100 份来源合成简历、8 份本地 PDF、10 份无关职业负例，以及 2 份人工编写的市场、体育压力样本。7 份原标为合成强匹配的复核记录见 `Samples_for_optimization/synthetic_100/review_labels.json`；来源清单不改。`status` 必须为 `complete` 才能解释指标；`mismatch_ids`、`inversion_ids` 和分位数列出分层问题。更改页面评分阈值后可用本地缓存复评，证据缓存按模型、阶段、岗位标准和正文摘要隔离。合成分数和模拟额度占比不能证明线上 ≥10% 的实际打招呼效果。

正式招聘与本地评测共用细化评分：`qwen-plus` 非思考模式返回逐项证据强度、任务相关性（各0至4）及简短理由；程序按岗位权重计算原始分 `Σ(weight × level × fit / 16)`。本体实施岗位另核对建模、SQL、编程、交付四项能力与硬条件，将原始分映射到合格、潜力、相关但有缺口、无关四档；最终分保留一位小数。其他未识别岗位使用通用评分。模型指定证据行号，由程序还原原文；无效证据纠正一次后仍无效则待复核。正式运行页面也显示匹配理由、规则调整及缺口。旧运行记录不会自动重算。

“载入测试岗位”同时设置粗筛阈值2、精筛阈值75。当前本地最终放行判断为120/120，但精筛“通过/复核/拒绝”三分类仅79/120；页面分别显示两种指标。阈值来自同一批样本调优，不能视为独立验证或其他岗位的默认推荐。评分公式、分层间隔、完整结果及复现指令见[评测记录](../records/llm_screening_evaluation_2026-10-16.md)。

日期快照 `qwen-plus-2025-07-28` 在当前账户实测返回模型不存在，因此默认使用已实测成功的 `qwen-plus`。所有推理在云端，无需本地模型。CLI 支持 `--workers 1` 至 `--workers 8`，默认4；评测缓存按提示词版本隔离。模型别名可能更新，长期对比时应重新确认服务端版本。

## 离线对比

`Samples_for_optimization` 包含 2 份人工认定高匹配、6 份人工拒绝的完整 PDF，以及 `external_negative` 下 10 份另行标记的 Apache 2.0 合成中文负例。负例来自 [SyntheticResumeData](https://github.com/jijunhao/SyntheticResumeData) 固定提交，抽取时排除了姓名和联系信息。负例只用于检查明显无关职业的误报，不能提高或替代 8 份真实样本的召回率统计。

在工作区根目录设置 `DASHSCOPE_API_KEY` 后运行以下命令；它仅向现有 Qwen API 发送测试简历，不连接 BOSS，不触发打招呼。脚本会使用本应用 `.runtime/benchmark_deps` 中单独安装的 `pypdf`；若迁移到新机器且没有 `pdftotext`，需先在该目录安装 `pypdf`。

```powershell
./recruitment_app/benchmark.ps1
```

报告分别给出旧评分与影子评分在 8 份真实样本上的精确率、召回率及 75/25 加权结果，并单列 10 份合成负例的误报数。只有完成 API 实测后，才能据此讨论阈值；这批样本都没有联系前卡片快照，不能测粗筛召回率，也不能证明每日 10% 的实际打招呼高匹配比例。
