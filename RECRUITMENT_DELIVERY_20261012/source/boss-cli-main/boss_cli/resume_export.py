"""Loss-preserving Markdown export of the returned profile, not PDF attachments."""
from __future__ import annotations

import hashlib
import re

LABELS = {'geekDetailInfo': '在线简历', 'geekBaseInfo': '基本信息', 'geekWorkExpList': '工作经历',
          'geekEduExpList': '教育经历', 'geekProjectExpList': '项目经历', 'description': '描述',
          'name': '姓名', 'company': '公司', 'companyName': '公司', 'positionName': '职位',
          'personalAdvantage': '个人优势', 'geekDesc': '个人介绍'}
SESSION_FIELDS = {'securityId', 'token', 'cookie', 'cookies', '__zp_stoken__', 'zp_token'}


def resume_name(data):
    detail = data.get('geekDetailInfo', data)
    base = detail.get('geekBaseInfo', detail)
    return str(base.get('name') or base.get('geekName') or 'candidate')


def default_filename(data, geek_id, job_id):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', resume_name(data)).strip(' .')[:60] or 'candidate'
    digest = hashlib.sha256(f'{geek_id}:{job_id}'.encode()).hexdigest()[:12]
    return f'{name}_{digest}_resume.md'


def render_resume(data, geek_id, job_id):
    lines = [f'# {resume_name(data)}', '', '> 来源：当前账号的在线简历接口返回；尚不代表与页面逐项核对后的完整简历。',
             '', '## 关联标识', '', f'- candidate_id: {geek_id}', f'- job_id: {job_id}', '',
             '## 简历字段', '', '以下保留返回字段，不按经历数量或正文长度截断；未知字段保留原字段名。', '']

    def visit(value, depth=0):
        prefix = '  ' * depth
        if isinstance(value, dict):
            for key, child in value.items():
                if key in SESSION_FIELDS:
                    continue
                label = LABELS.get(key, key)
                if isinstance(child, (dict, list)):
                    lines.append(f'{prefix}- **{label}**:')
                    visit(child, depth + 1)
                else:
                    text = str(child) if child is not None else '（无）'
                    lines.append(f'{prefix}- **{label}**: ' + text.replace('\n', '\n' + prefix + '  '))
        elif isinstance(value, list):
            for index, child in enumerate(value, 1):
                lines.append(f'{prefix}- 条目 {index}:')
                visit(child, depth + 1)
        else:
            lines.append(prefix + str(value))
    visit(data)
    return '\n'.join(lines).rstrip() + '\n'
