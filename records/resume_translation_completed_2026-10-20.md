# 简历中文翻译完成记录

- 用户于2026-10-20明确授权将选定的1997份公开英文简历发送至阿里云DashScope翻译并本地保存。
- Qwen-Turbo单次测试返回429 limit_requests，改用已验证可用的轻量模型Qwen-Flash；仅翻译使用Flash，未改招聘评分模型。
- 完成：1997份英文简历由Qwen-Flash翻译，另3份原有中文合成简历直接保留，共2000份中文简历。最终失败0份。
- 主批次使用32路并发、断点缓存及重试，耗时约13分钟；少量返回英文或格式不合格的输出经Qwen再次翻译补齐。Codex没有执行翻译。
- 中文TXT：`Samples_for_optimization/generic_2000/resumes_zh/Gxxxx.zh.txt`。
- 译文JSON：`Samples_for_optimization/generic_2000/translations/Gxxxx.json`，保留来源哈希、译文哈希、模型及待复核状态。
- 原始英文：`Samples_for_optimization/generic_2000/resumes_original/`，未覆盖。
- 最终校验：2000份全部通过来源哈希、译文哈希、中文存在性、TXT与JSON内容一致性检查。报告见`translation_verification.json`。
- 本次仅完成翻译和文件结构校验，未进行逐份语义忠实性复核、独立匹配标注或评分评测，不能据此声称匹配标签或评分机制已验收。
- 可续跑命令：设置`TRANSLATION_MODEL=qwen-flash`后运行`python -m matching_eval.translate_corpus`；异常重译为`python -m matching_eval.retry_translation`；本地校验为`python -m matching_eval.verify_translations`。Python应使用项目既有虚拟环境。
