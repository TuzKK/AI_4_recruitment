# boss-resume-filter 源码与真实采集样本

上游：https://github.com/yaoyouzhong/boss-resume-filter

固定提交：8a150c26f7ef06a90e2ed613fea20d55719b0f75。完整 ZIP 已下载并解压至 ../source/boss-resume-filter-8a150c26f7ef06a90e2ed613fea20d55719b0f75/。这是当前上游快照，不保证与已安装 EXE 相同。核心三个文件与单独取得的同提交文件逐字节一致。

## 1. 实际数据与清洗

已通过当前登录 Chrome 页面的只读 DOM 读取保存一份可见推荐候选人卡片：01-browser-visible-sample.private.json；直接阅读文字版：01-browser-visible-text.private.txt。共 492 字符、13 行。它不是完整在线简历，也不是 PDF 附件。JSON 外层采集时间、来源、范围字段为本次采样添加，不是项目原生输出。未调用模型或发送招呼。

项目 DOM 采集器 bossmaster.py:1761 返回 [{geek_id, name, text}]，text 是卡片 innerText，仍含换行及页面文本。另有接口响应解析路径：bossmaster.py:1863 把 geekCard 拼成带标签摘要，:1929 生成 educations、works、personal_summary 等结构化 _api_profile，:2047 转成候选人记录。此路径并不证明存在对外开放 API；本次没有捕获接口响应。

LLM 前还会加工：llm_eval.py:203 起统一空白，:347 构建摘要；优先用结构化 _api_profile，否则处理 summary。教育和工作各最多 5 条，技能标签去重最多 40 个，按字段截断，再按默认 4000 字符截断（另附省略号）。二次简历正文先截至 6000 字符。姓名等仍可能保留，因此清洗不等于脱敏。02-whitespace-cleaning-demo.private.txt 只复现空白归一、去空行，明确不冒充完整最终模型输入。

## 2. Prompt

matching-prompts.txt 保存从源码静态提取的四个匹配模板，已打印：_SYSTEM_PROMPT、_USER_TEMPLATE、_RESUME_SYSTEM_PROMPT、_RESUME_USER_TEMPLATE。位置为 llm_eval.py:141、164、174、194。岗位要求、硬条件、候选人摘要在运行时填入固定模板，然后调用用户配置的模型；不是调用 BOSS 原生 AI 评分。这里只导出与候选人匹配直接相关的四份模板，不宣称是项目所有辅助 AI 功能的全部提示词。

## 3. 分数

规则分 = min(100,25 + 技能分[0,50] + 经验分[0,15] + 学历分[0,10] + 优先项分[0,10])。

最终分 = clamp(规则分 + LLM调整值[-15,+15],0,100)。四维 1–10 分用于展示，不加总到最终分。规则已淘汰的人不会被 AI 加分救回。二次评估替换第一次调整值，不叠加。详细条件与静态发现见 scoring-audit.md。

这是源码审计及一次只读样本验证，不是软件全部功能的运行验收。
