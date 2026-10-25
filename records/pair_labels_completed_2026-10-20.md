# 简历与招聘要求标签生成完成

## 结果

已通过阿里云DashScope的Qwen-Plus API完成全部10000个配对的标注，覆盖2000份中文简历、100份招聘要求，每份简历5个岗位。最后全量本地校验通过，失败0。训练/验证/测试配对数保持6000/2000/2000。

| label_3 | 含义 | score范围 | 数量 | 平均分 |
| --- | --- | --- | ---: | ---: |
| 0 | 粗筛精筛均不通过 | 0至49.9 | 4964 | 28.08 |
| 1 | 仅通过粗筛 | 50至74.9 | 2343 | 63.09 |
| 2 | 两层均通过 | 75至100 | 2693 | 86.04 |

实际分数范围0–96.5，支持一位小数；不是录用概率。没有按预设比例强行分配标签。同一简历可以对不同岗位获得不同标签。

## 文件

- 全量JSON：`Samples_for_optimization/generic_2000/pair_labels_llm.json`
- 全量JSONL：`Samples_for_optimization/generic_2000/pair_labels_llm.jsonl`
- 分简历文件：`Samples_for_optimization/generic_2000/pair_labels_llm/Gxxxx.json`
- 校验报告：`Samples_for_optimization/generic_2000/pair_label_verification.json`
- 定义说明：`records/pair_label_definition_2026-10-20.md`
- 可复用脚本：`matching_eval/pair_labels_llm.py`，生成命令`python -m matching_eval.pair_labels_llm generate`，本地验证命令`python -m matching_eval.pair_labels_llm verify`；使用项目既有虚拟环境。

每条包含配对ID、简历ID、岗位ID、label_3、score、coarse_pass、fine_pass、中文理由、缺口、必备条件状态、简历/岗位原文引用、模型及版本、原分组。引用由模型选择编号、本地还原原文，避免模型改写引文。

## 校验与边界

22项单元测试通过；10000个配对通过数量、ID唯一性、来源上下文哈希、分数与阶段标签一致性、必备条件状态约束及引用存在性校验。生成过程没有运行现有评分器或读取其评分。

这是`llm_silver`自动标签，不是人工标准答案或独立语义复核结果。模型自行标记困难负例5125对、涉及1948份简历；这一标记未经独立核验，不能据此宣称困难负例质量目标已验收。引用存在只证明引用来自原文，不证明推理一定正确。

当前未修改网页默认评分机制，也未执行评分调优或锁定测试集验收。旧`pairs.json`中的空label仍表示旧版独立标签未完成；本轮新三值及连续标签以`pair_labels_llm.json/jsonl`为准。
