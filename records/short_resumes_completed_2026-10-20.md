# 中文粗筛短简历生成完成

- 2000份中文简历均已通过阿里云LLM API生成对应短简历词条；1941份Qwen-Flash，59份由Qwen-Plus补齐。无本地模型、无Codex手写词条。
- 输出目录：`Samples_for_optimization/generic_2000/short_resumes_zh/`，每份包含`Gxxxx.txt`与`Gxxxx.json`。
- 字数口径：去掉空白后按字符计数，英文每个字母、数字、标点均计一个字符。2000份均在100–200字符之间，平均156.9字符。
- JSON包含简历ID、模型、中文来源哈希、摘要哈希、字数及生成版本。来源为本地中文完整简历，不读取目标招聘要求，不生成匹配分数或标签。
- 自动检查：2000份ID、来源哈希、摘要哈希、中文存在性、长度、TXT/JSON一致性全部通过，最终失败0份。报告：`Samples_for_optimization/generic_2000/short_resume_verification.json`。
- 内容生成要求保留真实职责、关键技能、代表项目和教育信息，禁止虚构、夸大、写入姓名与联系方式。自动检查不等于逐份语义忠实性复核。
- 这是由完整简历压缩生成的模拟粗筛资料，并非真实BOSS卡片；后续评测应明确这一差别。本轮未修改线上筛选规则，也未把它当作独立匹配标签。
- 可复用脚本：`python -m matching_eval.generate_short_resumes`，环境变量`SHORT_RESUME_MODEL`默认`qwen-flash`，使用项目既有虚拟环境与`DASHSCOPE_API_KEY`。已存在且来源哈希一致的合格文件直接复用。
