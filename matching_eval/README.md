# 本体建模实施与交付岗位匹配评测

本目录是独立的离线评分模块，不调用 BOSS 联系接口，也不修改正在开发的信息源提取代码。岗位文本以 `Samples_for_optimization/recruitment_request.txt` 为准。样本原始 PDF 和含原文件名的 `manifest.json` 仅留在本机；`Samples_for_optimization/.gitignore` 排除它们。

## 输入与决策

联系前批量输入为 JSON：

```json
{
  "stage": "precontact",
  "records": [
    {
      "candidate_id": "anonymous-001",
      "text": "联系前实际可见的候选人资料",
      "coverage": "partial",
      "source": "boss_api_or_dom",
      "captured_at": "2026-10-13T12:00:00+08:00"
    }
  ]
}
```

`stage` 可为 `precontact` 或 `full_resume`；`coverage` 可为 `complete`、`partial`、`unknown`。`source` 与带时区的 `captured_at` 必填，整批记录会在发起模型请求前校验。粗筛只使用联系前可见内容。精筛读取完整简历，独立判断，不接收粗筛分数。输出包含 `score`、`decision`、逐项分数、可在输入原文定位的证据、未知项、问题、输入摘要和评估时间；结果不复制完整简历正文。

评分权重总计 100：数据接入、映射、清洗与初始化 25；实施交付、测试、排障与验收 25；SQL 15；Python/JavaScript 与 Logic 15；本体及数据建模 10；优先经验 10。模型只负责提取和分级证据，代码核对引用与能力类别是否相符，再计算分数与决策。完整简历的学历通过证据还需包含相关专业；无关或无法核验的证据转人工复核。未提及的条件保持未知；明确学历不符或明确拒绝现场/出差才可按硬条件拒绝，冲突证据转人工复核。

默认粗筛联系阈值 30，要求有具体数据实施或交付证据，以及至少一项技术支撑证据；否则保留为 `hold` 或 `review`。默认精筛高匹配阈值 75，且需本科学历相关证据、数据实施、交付、SQL 和代码证据。阈值可在命令中覆盖，调参结果不会自动写入默认值。联系队列只从 `contact` 中按分数选取，额度可空置。

## 本机命令

以下命令在工作区根目录运行，Python 可使用 `source/boss-cli-main/.venv/Scripts/python.exe`。PDF 阅读优先使用本机 Poppler 的 `pdftotext`，未安装时可用 `pypdf`。模型评测需要自行在本机配置新的 `DASHSCOPE_API_KEY` 和与该密钥地域/工作空间匹配的 `MATCHING_BASE_URL`；密钥不写入文件或命令参数。地址须为可信阿里云 DashScope 的 HTTPS 兼容接口。`--remote` 明确允许将本次输入的简历文本发往该接口。

```powershell
python -m matching_eval audit-samples
python -m matching_eval score-samples --remote --output matching_eval/.runtime/full_resume.json
python -m matching_eval benchmark --stage full_resume --predictions matching_eval/.runtime/full_resume.json
python -m matching_eval calibrate --stage full_resume --predictions matching_eval/.runtime/full_resume.json
python -m matching_eval score-records --input precontact-records.json --output matching_eval/.runtime/precontact.json --remote
python -m matching_eval rank-contacts --predictions matching_eval/.runtime/precontact.json --quota 20
```

`score-records` 和 `score-samples` 均支持 `--threshold 0..100`。单份文本可用 `score --stage precontact --candidate-id <ID> --text-file <TXT或MD> --coverage partial --remote`。评测结果保存在本机；`matching_eval/.gitignore` 排除运行结果。

基线比较要求两个预测文件的阶段与候选人 ID 集合一致：

```powershell
python -m matching_eval benchmark --stage full_resume --predictions matching_eval/.runtime/new.json --baseline matching_eval/.runtime/old.json
```

每天的真实联系效果使用已打招呼 ID 列表与**完成精筛、经人工确认**的标签映射计算：

```powershell
python -m matching_eval daily-yield --greeted greeted-ids.json --labels reviewed-labels.json
```

`greeted-ids.json` 是 ID 数组；`reviewed-labels.json` 是 `ID → high_match/rejected` 对象。没有打招呼时比例为 `null`，不会宣称达到或未达到 10%。

## 评测边界

现有 8 份去重样本为 2 正例、6 负例，均是完整 PDF。它们可以检验精筛与 PDF 文本读取，**不能代替联系前快照检验粗筛**。缺少样本预测时只报告已评估记录的原始精确率与召回率，不给总加权分或校准阈值；完整样本上的阈值搜索仍标为探索性。要比较粗筛召回率，需从另一终端取得同一候选人的真实联系前资料。每天 ≥10% 高匹配比例须用实际打招呼和人工复核记录监测，不能由这 8 份样本保证。

