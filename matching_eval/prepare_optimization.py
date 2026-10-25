"""Freeze inputs, audit development labels, and prepare unseen ontology labels."""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time

from .generic_corpus import CORPUS, ROOT, sha, write_json
from . import pair_labels_llm as labeling

OUT = CORPUS / 'optimization'
AUDIT_SYSTEM = labeling.SYSTEM + '''
你正在做一次独立盲复核。未提供之前的标签或评分器结果，请从原始证据重新判断。
重点区分职责相似和术语相似，核对初/中/高级要求，不将“未提及”判成明确不会。
逐项确认明确必备能力是否有直接或可迁移的事实支持，不能因为总体职业相近就判全部满足。
'''


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def freeze_inputs():
    labels = read(CORPUS / 'pair_labels_llm.json')['labels']
    pairs, jobs, groups = labeling.load_inputs()
    assert len(labels) == len(pairs) == 10000
    by_id = {r['pair_id']: r for r in labels}
    assert len(by_id) == 10000
    partitions = defaultdict(set)
    resume_splits, group_splits = defaultdict(set), defaultdict(set)
    for pair in pairs:
        assert pair['id'] in by_id
        assert pair['split'] == by_id[pair['id']]['split']
        partitions[pair['split']].add(pair['job_id'])
        resume_splits[pair['resume_id']].add(pair['split'])
        group_splits[pair['group']].add(pair['split'])
    assert all(len(v) == 1 for v in resume_splits.values())
    assert all(len(v) == 1 for v in group_splits.values())
    assert not partitions['test'] & (partitions['train'] | partitions['validation'])
    files = {}
    for name in ('pairs.json', 'jobs.json', 'pair_labels_llm.json'):
        files[name] = sha((CORPUS / name).read_text(encoding='utf-8'))
    for cid in groups:
        for folder in ('translations', 'short_resumes_zh'):
            path = CORPUS / folder / f'{cid}.json'
            files[f'{folder}/{cid}.json'] = sha(path.read_text(encoding='utf-8'))
    job = (ROOT / 'Samples_for_optimization/recruitment_request.txt').read_text(encoding='utf-8')
    files['ontology_original_jd'] = sha(job)
    freeze = {'schema_version': 1, 'files': files, 'split_pairs': dict(Counter(p['split'] for p in pairs)),
              'test_resume_ids': sorted(cid for cid, splits in resume_splits.items() if splits == {'test'}),
              'test_job_ids': sorted(partitions['test']), 'scoring_test_opened': False}
    path = OUT / 'input_freeze.json'
    if path.exists():
        if read(path) != freeze:
            raise ValueError('Frozen inputs changed; refuse to silently replace benchmark')
    else:
        write_json(path, freeze)
    chosen = []
    for label in (0, 1, 2):
        pool = [r for r in labels if r['split'] == 'train' and r['label_3'] == label]
        chosen.extend(sorted(pool, key=lambda r: sha(r['pair_id'] + 'audit-20261020'))[:100])
    assert len(chosen) == 300
    selection = {'pair_ids': sorted(r['pair_id'] for r in chosen), 'seed': 'audit-20261020',
                 'original_classes': dict(Counter(r['label_3'] for r in chosen))}
    if (OUT / 'audit_selection.json').exists():
        assert read(OUT / 'audit_selection.json') == selection
    else:
        write_json(OUT / 'audit_selection.json', selection)
    return pairs, jobs, groups, by_id, freeze, selection, job


def batch(groups, jobs, destination, system, name):
    labeling.DEST = destination
    labeling.SYSTEM = system
    destination.mkdir(parents=True, exist_ok=True)
    completed, errors = 0, []
    started = time.time()
    with ThreadPoolExecutor(max_workers=32) as pool:
        pending = {pool.submit(labeling.generate, cid, group, jobs): cid for cid, group in groups.items()}
        for future in as_completed(pending):
            cid = pending[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {'error': type(exc).__name__, 'resume_id': cid}
            if 'error' in result:
                errors.append(result)
            else:
                completed += len(result['labels'])
            progress = {'stage': name, 'completed_pairs': completed, 'errors': errors,
                        'elapsed_seconds': round(time.time() - started), 'status': 'running'}
            write_json(OUT / f'{name}_progress.json', progress)
            if (completed + len(errors)) % 25 == 0:
                print(json.dumps({**progress, 'errors': len(errors)}), flush=True)
    progress['status'] = 'complete' if not errors else 'incomplete'
    write_json(OUT / f'{name}_progress.json', progress)
    if errors:
        raise RuntimeError(f'{name}: {len(errors)} groups require retry')


def main():
    OUT.mkdir(exist_ok=True)
    pairs, jobs, groups, originals, frozen, selection, job = freeze_inputs()
    chosen = set(selection['pair_ids'])
    audit_groups = defaultdict(list)
    for pair in pairs:
        if pair['id'] in chosen:
            audit_groups[pair['resume_id']].append(pair)
    original_system = labeling.SYSTEM
    batch(audit_groups, jobs, OUT / 'audit', AUDIT_SYSTEM, 'audit')
    reviewed = {}
    for cid in audit_groups:
        result = read(OUT / 'audit' / f'{cid}.json')
        payload = labeling.context_for(cid, audit_groups[cid], jobs)
        assert result['context_sha256'] == labeling.context_hash(payload)
        reviewed.update({r['pair_id']: r for r in labeling.validate_labels(result, payload)})
    assert set(reviewed) == chosen
    revisions = [{'pair_id': pid, 'original': originals[pid], 'reviewed': reviewed[pid],
                  'changed': originals[pid]['label_3'] != reviewed[pid]['label_3'] or
                             originals[pid]['score'] != reviewed[pid]['score']}
                 for pid in sorted(chosen)]
    write_json(OUT / 'audit_revisions.json', {'review_type': 'same_model_independent_prompt_blind',
               'rows': revisions, 'class_changes': sum(r['original']['label_3'] != r['reviewed']['label_3'] for r in revisions)})
    development = [reviewed.get(p['id'], originals[p['id']]) for p in pairs if p['split'] != 'test']
    development_payload = {'status': 'frozen', 'label_source': 'llm_silver_with_300_blind_audit',
                           'labels': development}
    path = OUT / 'development_labels.json'
    if path.exists():
        assert read(path) == development_payload
    else:
        write_json(path, development_payload)
    ontology_groups = {}
    for cid in frozen['test_resume_ids']:
        ontology_groups[cid] = [{'id': f'{cid}_ONTOLOGY_ORIGINAL', 'resume_id': cid,
                                'job_id': 'ONTOLOGY_ORIGINAL', 'split': 'test', 'group': groups[cid][0]['group']}]
    ontology_jobs = {'ONTOLOGY_ORIGINAL': {'id': 'ONTOLOGY_ORIGINAL', 'text': job}}
    batch(ontology_groups, ontology_jobs, OUT / 'ontology_labels', original_system, 'ontology_truth')
    rows = []
    for cid in ontology_groups:
        result = read(OUT / 'ontology_labels' / f'{cid}.json')
        payload = labeling.context_for(cid, ontology_groups[cid], ontology_jobs)
        assert result['context_sha256'] == labeling.context_hash(payload)
        rows.extend(labeling.validate_labels(result, payload))
    assert len(rows) == 400
    write_json(OUT / 'ontology_truth.json', {'status': 'frozen', 'job': job, 'job_sha256': sha(job),
               'labels': rows, 'label_source': 'llm_silver', 'used_for_tuning': False})
    write_json(OUT / 'preparation_complete.json', {
        'status': 'complete', 'audited_pairs': 300, 'development_pairs': 8000,
        'cross_job_test_pairs': 2000, 'ontology_test_pairs': 400,
        'development_sha256': sha(path.read_text(encoding='utf-8')),
        'ontology_sha256': sha((OUT / 'ontology_truth.json').read_text(encoding='utf-8')),
        'test_scoring_started': False})
    print('Preparation complete; test scoring remains sealed.', flush=True)


if __name__ == '__main__':
    main()
