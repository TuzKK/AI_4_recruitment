"""Validate saved translations without any model calls."""
import json
import re
from collections import Counter
from .generic_corpus import CORPUS, sha, write_json


def run():
    source = json.loads((CORPUS / 'source_selection.json').read_text(encoding='utf-8'))
    errors, models, count = [], Counter(), 0
    for row in source['resumes']:
        cid = row['id']
        path = CORPUS / f'translations/{cid}.json'
        try:
            result = json.loads(path.read_text(encoding='utf-8'))
            text = result['text_zh']
            assert result['original_sha256'] == row['original_sha256'], 'source_hash'
            assert result['sha256'] == sha(text), 'translation_hash'
            assert len(re.findall(r'[\u3400-\u9fff]', text)) >= 80, 'chinese_text'
            target = CORPUS / f'resumes_zh/{cid}.zh.txt'
            if not target.exists():
                target.write_text(text, encoding='utf-8')
            assert target.read_text(encoding='utf-8') == text, 'txt_json_mismatch'
            models[result.get('translation_model', 'original_chinese')] += 1
            count += 1
        except Exception as exc:
            errors.append({'id': cid, 'error': type(exc).__name__})
    report = {'date': '2026-10-20', 'requested': len(source['resumes']), 'completed': count,
              'failures': errors, 'status': 'complete' if not errors else 'incomplete',
              'models': dict(models), 'review_status': 'structural_checks_only_not_semantically_reviewed',
              'checks': ['source_hash', 'translation_hash', 'chinese_text', 'txt_json_consistency'],
              'codex_translation_calls': 0}
    write_json(CORPUS / 'translation_verification.json', report)
    write_json(CORPUS / 'translation_progress.json', report)
    if not errors:
        source['status'] = 'translated_pending_independent_review'
        for row in source['resumes']:
            if row['language_original'] != 'zh':
                row['translation_status'] = 'translated_pending_independent_review'
        write_json(CORPUS / 'source_selection.json', source)
        integrity = json.loads((CORPUS / 'integrity_report.json').read_text(encoding='utf-8'))
        integrity['chinese_files'] = count
        integrity['translation_verification'] = 'translation_verification.json'
        write_json(CORPUS / 'integrity_report.json', integrity)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    run()
