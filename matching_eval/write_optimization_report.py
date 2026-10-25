"""Render the sealed offline evaluation into a concise local handoff."""
from datetime import datetime
import json
from .optimize_screening import OUT, ROOT, read, verify_artifact_ledger


def percentage(value):
    return '无适用分母' if value is None else f'{100*value:.2f}%'


def main():
    verify_artifact_ledger(read(OUT/'final_completion_seal.json'))
    result=read(OUT/'final_summary.json')
    frozen=read(OUT/'frozen_config.json')
    names={'final_cross_job':'跨岗位留出测试','final_ontology':'原始本体岗位留出测试','final_history':'历史样本回归'}
    approved=result['approved_for_default']
    lines=[
        '# 粗筛 / 精筛优化与最终测试',
        '',
        f'生成时间：{datetime.now().isoformat(timespec="seconds")}',
        '',
        '## 结论',
        '',
        ('离线验收门槛通过；是否切换应用默认配置需以应用配置记录为准。' if approved else
         '未达到全部离线验收门槛，保留应用原默认机制；不宣称本地样本已全部正确区分。'),
        '',
        '## 方法',
        '',
        '- 全程使用阿里云 Qwen API，无本地模型。LLM 抽取岗位规则与简历证据，本地规则计算分数。',
        '- 粗筛仅见中文短简历，精筛见完整中文正文；共享评分量尺，阶段阈值相差 25 分。',
        '- 训练 6,000 对、验证 2,000 对；按简历分组隔离测试，20 个岗位仅用于测试。',
        '- 300 对训练标签独立盲审后冻结；新数据是 LLM 银标签，不能视为人工金标准。',
        '- 配置由开发集选择后冻结，最终测试不参与调参。历史样本标签保持原样。',
        '',
        '## 最终测试',
        '',
        '| 数据集 | 匹配对 | 粗筛召回率 | 粗筛精确率 | 精筛精确率 | 全流程召回率 | 75/25 指标 |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for name,suite in result['suites'].items():
        m=suite['metrics']
        values=[names[name],str(m['rows']),percentage(m['coarse']['recall']),
                percentage(m['coarse']['precision']),percentage(m['fine']['precision']),
                percentage(m['pipeline']['recall']),percentage(m['weighted_75_25'])]
        lines.append('| '+' | '.join(values)+' |')
    lines+=['','精筛精确率仅统计粗筛通过人群；全流程召回率的分母包含所有 label=2，含粗筛漏掉的人。',
            '无分母的指标显示“无适用分母”，不能解释为 100%。','',
            '## 冻结配置','','```json',json.dumps(frozen['config'],ensure_ascii=False,indent=2),'```','',
            '## 分数层级','','| 数据集 | label=0 均分 | label=1 均分 | label=2 均分 |',
            '|---|---:|---:|---:|']
    for name in names:
        report=read(OUT/f'{name}.json')
        cells=[]
        for label in ('0','1','2'):
            value=report['fine_score_by_label'][label]['mean']
            cells.append('无有效分数' if value is None else f'{value:.1f}')
        lines.append('| '+' | '.join([names[name]]+cells)+' |')
    lines+=['','历史样本的具体层级：','',
            '| 层级 | 有效分数数量 | 精筛均分 | 中位数 |','|---|---:|---:|---:|']
    for tier,values in read(OUT/'final_history.json')['fine_score_by_tier'].items():
        lines.append(f"| {tier} | {values['count']} | {values['mean']:.1f} | {values['median']:.1f} |")
    lines+=['','## 限制与产物','',
            '- 各匹配对的粗筛/精筛分数、判定、简短理由、银标签原理由，均保存在对应 final_*.json。',
            '- 技术失败另记待复核，不从开发评测分母删除；最终测试严格要求证据校验成功。',
            '- 离线 Top-K 和高匹配占比不等于真实 BOSS 推荐流效果，不承诺每天固定产出比例。',
            '- R002 的历史 PDF 原文字层只有水印，已由云端视觉模型转录；N006/S090 使用 LLM 选择的原文片段摘要。',
            '- 本次未执行 BOSS 打招呼或发送消息。','',
            '完整数据目录：`Samples_for_optimization/generic_2000/optimization/`。']
    path=ROOT/'records/screening_optimization_final_2026-10-20.md'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(str(path),flush=True)


if __name__=='__main__':
    main()
