"""Inspect failed development rubric extraction without accessing holdout labels."""
from recruitment_app.core import _contains
from .optimize_screening import load_development, rubric_path, make_model, OUT, write_json
from recruitment_app.generic_model import RUBRIC_PROMPT
from .optimize_screening import get_text, read, score_generic
import sys


def main():
    rows, jobs = load_development(120)
    if len(sys.argv)>1:
        row=next(r for r in rows if r['pair_id']==sys.argv[1])
        tag='evidence-v1'
        job=jobs[row['job_id']]
        rubric=read(rubric_path(job,tag))
        text=get_text(row['resume_id'],'full_resume')
        result=make_model(tag).evidence_generic(rubric,text)
        checked=score_generic(rubric,text,result,'full_resume','complete',75)
        write_json(OUT/'evidence_diagnostics'/f"{row['pair_id']}.json",
                   {'judgement':result,'issues':checked['issues']})
        print(checked['issues'],flush=True)
        return
    for jid in sorted({r['job_id'] for r in rows}):
        job = jobs[jid]
        if rubric_path(job, 'baseline').exists():
            continue
        model = make_model('baseline')
        raw = model._ask(RUBRIC_PROMPT, job)
        invalid = [i for group in ('criteria', 'requirements') for i in raw.get(group, [])
                   if not _contains(job, i.get('jd_quote', ''))]
        write_json(OUT / 'rubric_diagnostics' / f'{jid}_response.json',
                   {'job': job, 'response': raw, 'invalid_quotes': invalid})
        print(jid, invalid, flush=True)


if __name__ == '__main__':
    main()
