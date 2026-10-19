"""Resumable corpus preparation. Source labels are never treated as pair gold labels."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'Samples_for_optimization/generic_2000'
DATA_CATEGORIES = ['Data Science', 'ETL Developer', 'SQL Developer', 'Database', 'Python Developer']
IT_CATEGORIES = ['Java Developer', 'Testing', 'Network Security Engineer', 'DotNet Developer',
                 'Web Designing', 'DevOps', 'Information Technology', 'React Developer']
DIRECTIONS = ['LLM应用', 'Agent', 'RAG', '机器学习', '算法研究', 'NLP', '计算机视觉', '推荐算法',
              'MLOps', 'AI平台', '数据工程', '数据分析', '数据治理', '本体实施', 'Python后端',
              'Java后端', '全栈', '前端', '测试开发', '云平台运维']


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def codex_json(prompt, output):
    """Use the logged-in Codex hosted model; no local model, no API credentials in files."""
    if output.exists():
        return json.loads(output.read_text(encoding='utf-8'))
    output.parent.mkdir(parents=True, exist_ok=True)
    prompt = 'Do not use tools or browse. Return only a JSON object, no Markdown.\n' + prompt
    raw = output.with_suffix('.raw.txt')
    executable = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/OpenAI/Codex/bin/codex.exe'
    with output.with_suffix('.log').open('w', encoding='utf-8') as log:
        completed = subprocess.run([str(executable), 'exec', '--ephemeral', '--skip-git-repo-check',
            '--sandbox', 'read-only', '--color', 'never',
            '-o', str(raw), '-'], input=prompt, encoding='utf-8', stdout=log, stderr=log,
            cwd=ROOT, timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if completed.returncode:
        raise RuntimeError(f'Codex failed; inspect {output.with_suffix(".log")}')
    text = raw.read_text(encoding='utf-8').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError('Codex必须返回JSON对象')
    write_json(output, result)
    return result


def prepare_sources():
    source = CORPUS / 'sources/resume_atlas.csv'
    rows = list(csv.DictReader(source.open(encoding='utf-8', newline='')))
    seen, pools = set(), {'data': [], 'it': []}
    for index, row in enumerate(rows):
        category = row['Category']
        group = 'data' if category in DATA_CATEGORIES else 'it' if category in IT_CATEGORIES else None
        if group is None:
            continue
        text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL]', row['Text'])
        text = re.sub(r'(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)', '[PHONE]', text)
        text = re.sub(r'(?:https?://|www\.)\S+', '[URL]', text, flags=re.I)
        normalized = re.sub(r'\W+', ' ', text.lower()).strip()
        key = sha(normalized)
        if key in seen or len(text) < 400 or len(text) > 12000:
            continue
        seen.add(key)
        pools[group].append({'source_row': index, 'category': category, 'text_original': text,
                             'source': 'ahmedheakl/resume-atlas', 'source_type': 'open_dataset',
                             'original_sha256': key, 'language_original': 'en'})
    for values in pools.values():
        values.sort(key=lambda v: sha(v['original_sha256'] + '20261019'))
    chosen = pools['data'][:1200] + pools['it'][:800]
    for index, row in enumerate(chosen, 1):
        row['id'] = f'G{index:04d}'
        row['translation_status'] = 'pending'
    supplement = json.loads((CORPUS / 'sources/codex_synthetic_supplement.json').read_text(encoding='utf-8'))
    for item in supplement['resumes'][:2000-len(chosen)]:
        row = {**item, 'id': f'G{len(chosen)+1:04d}', 'text_original': item['text_zh'],
               'source': 'codex_synthetic_supplement', 'source_type': 'codex_synthetic',
               'original_sha256': sha(re.sub(r'\W+', ' ', item['text_zh'].lower()).strip()),
               'language_original': 'zh', 'translation_status': 'not_needed'}
        chosen.append(row)
        write_json(CORPUS / f'translations/{row["id"]}.json', {
            'id': row['id'], 'text_zh': item['text_zh'], 'original_sha256': row['original_sha256'],
            'sha256': sha(item['text_zh']), 'translation_status': 'not_needed',
            'source': row['source'], 'category': row['category']})
    write_json(CORPUS / 'source_selection.json', {'status': 'pending_translation',
        'source_counts': {k: len(v) for k, v in pools.items()}, 'selected_count': len(chosen),
        'target': 2000, 'shortfall': 2000-len(chosen), 'resumes': chosen})
    for row in chosen:
        path=CORPUS / 'resumes_original' / f'{row["id"]}.{row["language_original"]}.txt'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(row['text_original'],encoding='utf-8')
    print(json.dumps({'available': {k: len(v) for k,v in pools.items()}, 'selected': len(chosen)}, ensure_ascii=False), flush=True)


def build_jobs():
    jobs = []
    for offset in range(0, len(DIRECTIONS), 4):
        directions = DIRECTIONS[offset:offset+4]
        prompt = ('编写中文IT招聘要求用于独立评测，不读取任何候选人。以下每个方向写5份不同职位要求，'
                  '不是仅替换名称，分别覆盖初级、中级、高级、行业业务场景、平台交付场景。'
                  '每份200至350个中文字符，明确职位名称、实际职责、必备能力、优先条件；必要时给合理年限，'
                  '不要无故增加学历等限制。返回{"jobs":[{"direction":"方向","variant":1,"title":"...",'
                  '"text":"完整招聘需求"}]}。每个方向variant恰为1至5。方向：' + json.dumps(directions, ensure_ascii=False))
        result = codex_json(prompt, CORPUS / f'authoring/jobs_{offset:02d}.json')
        batch = result.get('jobs', [])
        expected = {(d, i) for d in directions for i in range(1,6)}
        if len(batch) != 20 or {(j['direction'],j['variant']) for j in batch} != expected:
            raise ValueError('招聘要求批次缺项或重复')
        for j in batch:
            if not isinstance(j['text'], str) or len(j['text']) < 180:
                raise ValueError('招聘要求过短')
            j.update(id=f'J{DIRECTIONS.index(j["direction"])*5+j["variant"]:03d}',
                     split='test' if j['variant']==5 else 'development', author='Codex',
                     sha256=sha(j['text']))
        jobs.extend(batch)
        write_json(CORPUS / 'jobs.json', {'status': 'complete' if len(jobs)==100 else 'in_progress', 'jobs': jobs})
        print(f'招聘要求 {len(jobs)}/100', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['sources','jobs'])
    args = parser.parse_args()
    {'sources': prepare_sources, 'jobs': build_jobs}[args.action]()
