import json
import re
from pathlib import Path

root = Path(__file__).parent / 'clean-resumes-20260929'
normalize = lambda value: re.sub(r'\s+', '', value)
index = ['# 在线简历清理结果', '', '本批次新增抓取 5 位已有沟通候选人。正文来源于本地接口返回，不使用 LLM 摘要或改写。', '',
         '统一模块：基本信息、个人介绍、期望职位、工作经历、项目经历、教育经历、专业技能、荣誉与证书。无内容的模块省略；同一条目完全相同的展示文本去重。', '',
         '清理核验仅证明选取的简历正文字段在 Markdown 中保留，不代表与网站全部可见模块逐项核对。原始 JSON 留存供审计。', '',
         '| 姓名 | Markdown | 字符数 | 核验正文段数 |', '|---|---|---:|---:|']
for source in sorted(root.glob('*.raw.private.json')):
    raw = json.loads(source.read_text(encoding='utf-8'))
    detail = raw['geekDetailInfo']
    base = detail['geekBaseInfo']
    lines = ['# ' + base['name'], '', '## 基本信息', '',
             ' | '.join(str(base[k]) for k in ['ageDesc', 'degreeCategory', 'workYearDesc', 'applyStatusDesc'] if base.get(k)), '']
    retained = []

    def text(value):
        if isinstance(value, str) and value.strip():
            retained.append(value)
            lines.extend([value.replace('\r\n', '\n').replace('\r', '\n'), ''])

    def paragraphs(item, keys):
        seen = set()
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip() and normalize(value) not in seen:
                text(value)
                seen.add(normalize(value))

    if base.get('userDescription'):
        lines.extend(['## 个人介绍', ''])
        text(base['userDescription'])
    expectations = list(detail.get('geekExpPosList') or [])
    shown = detail.get('showExpectPosition')
    if isinstance(shown, dict):
        expectations.append(shown)
    if expectations:
        lines.extend(['## 期望职位', ''])
        seen = set()
        for item in expectations:
            row = ' | '.join(str(item[k]) for k in ['locationName', 'positionName', 'industryDesc', 'salaryDesc'] if item.get(k))
            if row and row not in seen:
                text(row)
                seen.add(row)
    for title, key, heading, role, bodykeys in [
        ('工作经历', 'geekWorkExpList', 'company', 'positionName', ['responsibility', 'workPerformance', 'workEmphasis', 'description', 'workDesc']),
        ('项目经历', 'geekProjExpList', 'name', 'roleName', ['projectDescription', 'performance', 'description', 'projectDesc', 'url']),
        ('教育经历', 'geekEduExpList', 'school', 'major', ['eduDescription', 'courseDesc', 'briefIntroduce', 'thesisTitle', 'thesisDesc']),
    ]:
        entries = detail.get(key) or []
        if not entries:
            continue
        lines.extend(['## ' + title, ''])
        for item in entries:
            lines.extend(['### ' + str(item.get(heading) or '未填写名称'), ''])
            start = item.get('startYearMonStr') or item.get('startDateDesc') or item.get('startDate') or ''
            end = item.get('endYearMonStr') or item.get('endDateDesc') or item.get('endDate') or ''
            text(' | '.join(str(v) for v in [item.get(role), item.get('degreeName') if key == 'geekEduExpList' else item.get('department'), f'{start} - {end}' if start or end else ''] if v))
            paragraphs(item, bodykeys)
    if detail.get('professionalSkill'):
        lines.extend(['## 专业技能', ''])
        text(detail['professionalSkill'])
    for title, key, fields in [
        ('所获荣誉', 'geekHonorList', ['honorName', 'description']),
        ('资格证书', 'geekCertificationList', ['certName', 'description']),
    ]:
        if detail.get(key):
            lines.extend(['## ' + title, ''])
            for item in detail[key]:
                paragraphs(item, fields)
    # Preserve substantive text in uncommon resume modules without inventing a schema.
    for key, title in [('geekClubExpList','社团经历'), ('geekTrainingExpList','培训经历'), ('geekVolunteerExpList','志愿经历'), ('geekDesignWorksList','设计作品'), ('geekResumeProductList','作品集'), ('geekSocialContactList','社交信息')]:
        entries = detail.get(key)
        if entries:
            lines.extend(['## ' + title, ''])
            def walk(value):
                if isinstance(value, dict):
                    for field, child in value.items():
                        if re.search(r'id$|code$|highlight|icon|security|token', field, re.I):
                            continue
                        walk(child)
                elif isinstance(value, list):
                    for child in value:
                        walk(child)
                elif isinstance(value, str):
                    text(value)
            walk(entries)
    output = '\n'.join(lines).rstrip() + '\n'
    assert all(normalize(value) in normalize(output) for value in retained)
    # Independently check key long narrative fields from the raw response.
    expected = [base.get('userDescription', ''), detail.get('professionalSkill', '')]
    for key, fields in [('geekWorkExpList', ['responsibility','workPerformance','workEmphasis']), ('geekProjExpList', ['projectDescription','performance']), ('geekEduExpList', ['eduDescription','courseDesc','briefIntroduce','thesisTitle','thesisDesc'])]:
        for item in detail.get(key) or []:
            expected.extend(item.get(field, '') for field in fields)
    expected = [value for value in expected if isinstance(value, str) and value.strip()]
    assert all(normalize(value) in normalize(output) for value in expected), source.name
    name = re.sub(r'[<>:"/\\|?*]', '_', base['name'])
    filename = source.name[:2] + '-' + name + '.md'
    (root / filename).write_text(output, encoding='utf-8')
    index.append(f'| {name} | [{filename}]({filename}) | {len(output)} | {len(expected)} / {len(expected)} |')
    print(json.dumps({'file': filename, 'characters': len(output), 'narrative_checks_passed': len(expected)}, ensure_ascii=False))
(root / 'README.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
