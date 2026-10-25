"""Resume-safe, resumable cloud translation batch; no Codex translation calls."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from .generic_batch import translate_one
from .generic_corpus import CORPUS, write_json


def run():
    rows = json.loads((CORPUS / 'source_selection.json').read_text(encoding='utf-8'))['resumes']
    started = time.time()
    completed, errors = [], []
    text_dir = CORPUS / 'resumes_zh'
    text_dir.mkdir(exist_ok=True)

    def work(row):
        for attempt in range(4):
            try:
                result = translate_one(row)
                (text_dir / (row['id'] + '.zh.txt')).write_text(result['text_zh'], encoding='utf-8')
                return result
            except Exception as exc:
                if attempt == 3:
                    return {'id': row['id'], 'error': type(exc).__name__,
                            'http_status': getattr(getattr(exc, 'response', None), 'status_code', None)}
                time.sleep(2 ** (attempt + 1))

    with ThreadPoolExecutor(max_workers=32) as pool:
        futures = [pool.submit(work, row) for row in rows]
        for future in as_completed(futures):
            result = future.result()
            (errors if 'error' in result else completed).append(result if 'error' in result else result['id'])
            report = {'requested': len(rows), 'completed': len(completed), 'failures': errors,
                      'elapsed_seconds': round(time.time() - started),
                      'status': 'running', 'translator': os.environ.get('TRANSLATION_MODEL', 'qwen-turbo'),
                      'review_status': 'not_semantically_reviewed'}
            write_json(CORPUS / 'translation_progress.json', report)
            if (len(completed) + len(errors)) % 25 == 0:
                print(json.dumps(report), flush=True)
    report['status'] = 'complete' if not errors else 'incomplete'
    write_json(CORPUS / 'translation_progress.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    run()
