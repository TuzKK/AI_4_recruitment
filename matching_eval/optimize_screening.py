"""Versioned API-only development evaluation, rule search and sealed final tests."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import itertools
import json
import math
import re
from pathlib import Path
import statistics
import time
from functools import lru_cache

from recruitment_app.generic_model import GenericJobModel, PROMPT_VERSION, RUBRIC_PROMPT, EVIDENCE_PROMPT
from recruitment_app.generic_scoring import score_generic, criterion_weights
from .generic_corpus import CORPUS, ROOT, sha, write_json
from .prepare_optimization import OUT, read
from .api_guard import AccountBlocked, guard_model

BASE = {'weights':{'core':60,'skill':30,'bonus':10}, 'unknown_prior':35,
        'coarse_coverage':40,'fine_coverage':80,'coarse_threshold':50,'fine_threshold':75}
MODEL = 'qwen-plus'
REVIEW_TAGS = ('evidence-v3-hybrid-reviewed1', 'evidence-v3-hybrid-reviewed2')


def digest(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False))


def binary(truth, predicted):
    tp=sum(a and b for a,b in zip(truth,predicted))
    fp=sum(not a and b for a,b in zip(truth,predicted))
    fn=sum(a and not b for a,b in zip(truth,predicted))
    tn=sum(not a and not b for a,b in zip(truth,predicted))
    return {'tp':tp,'fp':fp,'fn':fn,'tn':tn,
            'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None}


def metrics(rows, coarse, fine, fine_scores, technical_reviews=None):
    truth=[r['label_3']==2 for r in rows]
    selected=[a and b for a,b in zip(coarse,fine)]
    cm=binary([r['label_3']>=1 for r in rows if r.get('coarse_labeled',True)],
              [c for r,c in zip(rows,coarse) if r.get('coarse_labeled',True)])
    fm=binary([t for t,c in zip(truth,coarse) if c],[f for f,c in zip(fine,coarse) if c])
    pm=binary(truth,selected)
    recalls=binary(truth,coarse)
    objective = (.75*pm['recall'] + .25*pm['precision']) if pm['recall'] is not None and pm['precision'] is not None else None
    matrix=[[0]*3 for _ in range(3)]
    for row,c,f in zip(rows,coarse,fine):
        if row.get('coarse_labeled',True):
            matrix[row['label_3']][2 if c and f else 1 if c else 0]+=1
    errors=[abs(s-r['score']) for r,s in zip(rows,fine_scores) if s is not None and type(r.get('score')) in (int,float)]
    return {'coarse':cm,'fine':fm,'pipeline':pm,'qualified_coarse_recall':recalls['recall'],
            'coarse_high_fit_yield':sum(t and c for t,c in zip(truth,coarse))/sum(coarse) if any(coarse) else None,
            'weighted_75_25':objective,'confusion_matrix':matrix,
            'three_class_accuracy':sum(matrix[i][i] for i in range(3))/sum(map(sum,matrix)) if sum(map(sum,matrix)) else None,
            'fine_score_mae':statistics.mean(errors) if errors else None,
            'fine_calls':sum(coarse), 'rows':len(rows),
            'technical_review_count':sum(technical_reviews or [])}


def meets(result):
    return result.get('technical_review_count',0)==0 and all(result[group][key] is not None and result[group][key]>=bound
               for group,key,bound in [('coarse','recall',.90),('coarse','precision',.70),
                                       ('fine','precision',.95),('pipeline','recall',.85)])


def authorize_test(directory, config, data_hash):
    path=directory/'frozen_config.json'
    if not path.exists():
        raise ValueError('Final test requires frozen configuration')
    frozen=read(path)
    if frozen['config']!=config or frozen['data_hash']!=data_hash:
        raise ValueError('Final test config or data differs from frozen version')
    if frozen.get('implementation_hashes') != implementation_hashes():
        raise ValueError('Implementation changed after freeze')
    opened=directory/'test_opened.json'
    identity={'config_hash':digest(config),'data_hash':data_hash,
              'implementation_hashes':implementation_hashes()}
    if opened.exists() and read(opened)!=identity:
        raise ValueError('Holdout already opened with a different implementation; new benchmark required')
    if not opened.exists():
        write_json(opened,identity)


def assert_inputs():
    expected=read(OUT/'input_freeze.json')['files']
    for name,wanted in expected.items():
        path=(ROOT/'Samples_for_optimization/recruitment_request.txt') if name=='ontology_original_jd' else CORPUS/name
        if sha(path.read_text(encoding='utf-8'))!=wanted:
            raise ValueError(f'Frozen input changed: {name}')
    prepared=read(OUT/'preparation_complete.json')
    if sha((OUT/'development_labels.json').read_text(encoding='utf-8'))!=prepared['development_sha256']:
        raise ValueError('Development labels changed after audit')
    if sha((OUT/'ontology_truth.json').read_text(encoding='utf-8'))!=prepared['ontology_sha256']:
        raise ValueError('Ontology truth changed')


def all_data_hash():
    return digest({'inputs':read(OUT/'input_freeze.json'),'prepared':read(OUT/'preparation_complete.json'),
                   'history':read(OUT/'history/manifest.json')})


def implementation_hashes():
    names=['recruitment_app/generic_scoring.py','recruitment_app/generic_model.py',
           'recruitment_app/core.py','recruitment_app/llm.py','matching_eval/optimize_screening.py',
           'matching_eval/api_guard.py']
    names.append('matching_eval/flash_format.py')
    names.append('recruitment_app/hybrid_model.py')
    for optional in ('matching_eval/screening_prompt_variants.py','matching_eval/screening_prompt_v2.py',
                     'matching_eval/screening_prompt_v3.py'):
        if (ROOT/optional).exists():
            names.append(optional)
    return {name:sha((ROOT/name).read_text(encoding='utf-8')) for name in names}


@lru_cache(maxsize=None)
def ensure_extractor_identity(prompt_tag):
    if prompt_tag in REVIEW_TAGS:
        parent = ensure_extractor_identity('evidence-v3-hybrid-format1')
        identity = {'parent': parent, 'review_policy': 'issues-or-null-or-score45to55',
                    'source': sha((ROOT/'recruitment_app/hybrid_model.py').read_text(encoding='utf-8'))}
        path = OUT/'extractor_identities'/f'{prompt_tag}.json'
        if path.exists() and read(path) != identity:
            raise ValueError('Review policy changed under existing identity')
        if not path.exists():
            write_json(path, identity)
        return identity
    if prompt_tag == 'evidence-v3-hybrid-format1':
        parent = ensure_extractor_identity('evidence-v3-hybrid')
        identity = {'parent': parent, 'format_adapter': sha((ROOT/'matching_eval/flash_format.py').read_text(encoding='utf-8'))}
        path = OUT/'extractor_identities'/f'{prompt_tag}.json'
        if path.exists() and read(path) != identity:
            raise ValueError('Format adapter changed under existing identity')
        if not path.exists():
            write_json(path, identity)
        return identity
    if prompt_tag == 'evidence-v3-hybrid':
        parent = ensure_extractor_identity('evidence-v3')
        identity = {'parent': parent, 'models': {'precontact': 'qwen-flash', 'full_resume': MODEL}}
        path = OUT/'extractor_identities'/f'{prompt_tag}.json'
        if path.exists() and read(path) != identity:
            raise ValueError('Hybrid extractor identity changed')
        if not path.exists():
            write_json(path, identity)
        return identity
    if prompt_tag=='evidence-v3':
        ensure_extractor_identity('evidence-v2')
    names=['recruitment_app/generic_model.py','recruitment_app/core.py','recruitment_app/llm.py']
    if prompt_tag!='baseline':
        names.append('matching_eval/screening_prompt_variants.py')
    if prompt_tag in ('evidence-v2','evidence-v3'):
        names.append('matching_eval/screening_prompt_v2.py')
    if prompt_tag=='evidence-v3':
        names.append('matching_eval/screening_prompt_v3.py')
    identity={'model':MODEL,'prompt_tag':prompt_tag,
              'sources':{name:sha((ROOT/name).read_text(encoding='utf-8')) for name in names}}
    path=OUT/'extractor_identities'/f'{prompt_tag}.json'
    if path.exists() and read(path)!=identity:
        raise ValueError('Extractor changed under an existing tag; use a new prompt tag')
    if not path.exists():
        write_json(path,identity)
    return identity


def load_development(limit=None):
    assert_inputs()
    rows=read(OUT/'development_labels.json')['labels']
    if limit:
        ids=sorted({r['resume_id'] for r in rows if r['split']=='train'},key=lambda c:sha(c+'pilot'))[:limit]
        rows=[r for r in rows if r['resume_id'] in set(ids)]
    return rows, {j['id']:j['text'] for j in read(CORPUS/'jobs.json')['jobs']}


def get_text(cid,stage):
    if cid.startswith('H_'):
        return read(OUT/f'history/texts/{cid}.json')['short' if stage=='precontact' else 'full']
    folder='short_resumes_zh' if stage=='precontact' else 'translations'
    return read(CORPUS/f'{folder}/{cid}.json')['text_zh']


def rubric_path(job, prompt_tag):
    if prompt_tag in REVIEW_TAGS:
        prompt_tag = 'evidence-v3-hybrid-format1'
    if prompt_tag == 'evidence-v3-hybrid-format1':
        prompt_tag = 'evidence-v3-hybrid'
    if prompt_tag == 'evidence-v3-hybrid':
        prompt_tag = 'evidence-v3'
    # v3 inherits the exact immutable v2 rubric method; reuse its job-only artifacts.
    if prompt_tag=='evidence-v3':
        prompt_tag='evidence-v2'
    return OUT/'rubrics'/f'{sha(job+RUBRIC_PROMPT+prompt_tag+MODEL)}.json'


def evidence_path(job, rubric, text, stage, prompt_tag):
    if prompt_tag in ('evidence-v3-hybrid-format1', *REVIEW_TAGS) and stage == 'full_resume':
        prompt_tag = 'evidence-v3-hybrid'
    model_name = MODEL
    if prompt_tag in ('evidence-v3-hybrid-format1', *REVIEW_TAGS) and stage == 'precontact':
        model_name = 'qwen-flash' if prompt_tag.endswith('format1') else 'qwen-flash+qwen-plus'
    if prompt_tag == 'evidence-v3-hybrid':
        prompt_tag = 'evidence-v3'
        if stage == 'precontact':
            model_name = 'qwen-flash'
    key=digest({'job':job,'rubric':rubric,'text':text,'stage':stage,'prompt_tag':prompt_tag,
                'prompt':EVIDENCE_PROMPT,'model':model_name})
    return OUT/'evidence'/f'{key}.json'


def make_model(prompt_tag, stage=None):
    if prompt_tag in REVIEW_TAGS:
        prompt_tag = 'evidence-v3-hybrid-format1'
    format_repair = prompt_tag == 'evidence-v3-hybrid-format1' and stage == 'precontact'
    if prompt_tag == 'evidence-v3-hybrid-format1':
        prompt_tag = 'evidence-v3-hybrid'
    model_name = MODEL
    if prompt_tag == 'evidence-v3-hybrid':
        prompt_tag = 'evidence-v3'
        if stage == 'precontact':
            model_name = 'qwen-flash'
    model=GenericJobModel.from_environment()
    model.model=MODEL
    if prompt_tag!='baseline':
        if prompt_tag=='evidence-v3':
            from .screening_prompt_v3 import BoundedJobModel as OptimizedModel
        elif prompt_tag=='evidence-v2':
            from .screening_prompt_v2 import AtomicJobModel as OptimizedModel
        elif prompt_tag=='evidence-v1':
            from .screening_prompt_variants import OptimizedModel
        else:
            raise ValueError('Unknown extractor version')
        model=OptimizedModel.from_environment()
        model.model=MODEL
        model.variant=prompt_tag
    model.model = model_name
    if format_repair:
        from .flash_format import wrap_format
        model = wrap_format(model)
    return guard_model(model)


def get_rubric(job,prompt_tag):
    ensure_extractor_identity(prompt_tag)
    path=rubric_path(job,prompt_tag)
    if path.exists():
        return read(path)
    last=None; correction=''
    for attempt in range(5):
        raw={}
        try:
            model=make_model(prompt_tag)
            ask=model._ask
            def capture(system,user):
                nonlocal raw
                raw=ask(system+correction,user)
                return raw
            model._ask=capture
            rubric=model.rubric(job)
            write_json(path,rubric)
            return rubric
        except AccountBlocked:
            raise
        except Exception as exc:
            last=exc
            correction='\n上次输出未通过结构校验：'+str(exc)[:400]+'。修正后严格返回JSON，引用必须来自原招聘原文。'
            from recruitment_app.core import _contains
            invalid=[item.get('jd_quote') for group in ('criteria','requirements')
                     for item in raw.get(group,[]) if isinstance(item,dict)
                     and isinstance(item.get('jd_quote'),str)
                     and not _contains(job,item['jd_quote'])]
            if invalid:
                correction+='\n这些引用不是连续原文：'+json.dumps(invalid,ensure_ascii=False)
                correction+='。禁止拼接不同位置句子、增删字或改写；每项只选一段实际连续原文。'
            correction+='\n评分项和硬条件的key必须全局唯一，只用短小写英文和下划线，长度2至40。建议评分项用crit_one等，硬条件用req_one等，不能复用。'
            write_json(OUT/'rubric_diagnostics'/f'{sha(job+prompt_tag)}.json',
                       {'error':type(exc).__name__,'detail':str(exc)[:400],'attempt':attempt+1,
                        'keys':{group:[i.get('key') for i in raw.get(group,[]) if isinstance(i,dict)]
                                for group in ('criteria','requirements')}})
            time.sleep(1+attempt)
    raise last


def get_evidence(job,rubric,text,stage,prompt_tag):
    ensure_extractor_identity(prompt_tag)
    path=evidence_path(job,rubric,text,stage,prompt_tag)
    if path.exists():
        return read(path)
    if prompt_tag in REVIEW_TAGS:
        if stage == 'full_resume':
            return get_evidence(job, rubric, text, stage, 'evidence-v3')
        if prompt_tag.endswith('reviewed2'):
            previous_path = evidence_path(job, rubric, text, stage, REVIEW_TAGS[0])
            if previous_path.exists():
                result = read(previous_path)
                checked = score_generic(rubric, text, result, stage, 'partial', 50)
                if not checked['issues']:
                    write_json(path, result)
                    return result
        from recruitment_app.hybrid_model import needs_plus_review
        try:
            result = get_evidence(job, rubric, text, stage, 'evidence-v3-hybrid-format1')
            scored = score_generic(rubric, text, result, stage, 'partial', 50)
            review = needs_plus_review(scored, 50)
        except ValueError:
            review = True
        if review:
            try:
                result = {**get_evidence(job, rubric, text, stage, 'evidence-v3'),
                          '_routing': {'model': MODEL, 'reviewed_from': 'qwen-flash'}}
            except AccountBlocked:
                raise
            except Exception as exc:
                write_json(path.with_suffix('.error.json'),
                           {'errors': [type(exc).__name__ + ': ' + str(exc)[:400]]})
                raise
        else:
            result = {**result, '_routing': {'model': 'qwen-flash'}}
        write_json(path, result)
        return result
    if prompt_tag == 'evidence-v3-hybrid-format1' and stage == 'precontact':
        legacy_path = evidence_path(job, rubric, text, stage, 'evidence-v3-hybrid')
        if legacy_path.exists():
            result = read(legacy_path)
            checked = score_generic(rubric, text, result, stage, 'partial', 50)
            if not checked['issues']:
                write_json(path, result)
                return result
    model=make_model(prompt_tag,stage)
    errors=None
    judgement=None
    previous_error=path.with_suffix('.error.json')
    if (not previous_error.exists() and prompt_tag == 'evidence-v3-hybrid-format1'
            and stage == 'precontact'):
        previous_error = evidence_path(job, rubric, text, stage, 'evidence-v3-hybrid').with_suffix('.error.json')
    if previous_error.exists():
        previous=read(previous_error)
        if previous.get('last_judgement'):
            if prompt_tag == 'evidence-v3-hybrid-format1' and stage == 'precontact':
                from .flash_format import normalize_fields
                raw = previous['last_judgement']
                fixed = normalize_fields(raw, rubric)
                if fixed != raw:
                    recovery = make_model(prompt_tag, stage)
                    recovery._ask = lambda system, user: fixed
                    restored = recovery.evidence_generic(rubric, text)
                    try:
                        checked = score_generic(rubric, text, restored, stage, 'partial', 50)
                        if not checked['issues']:
                            write_json(path, restored)
                            return restored
                    except (ValueError, TypeError):
                        pass
            errors=[e for e in previous.get('errors',[]) if not any(
                marker in e for marker in ('HTTPStatusError','ReadTimeout','ConnectError'))]
            errors.append('上次输出：'+json.dumps(previous['last_judgement'],ensure_ascii=False))
    for attempt in range(3):
        try:
            judgement=model.evidence_generic(rubric,text,errors)
            checked=score_generic(rubric,text,judgement,stage,'partial' if stage=='precontact' else 'complete',
                                  50 if stage=='precontact' else 75)
            if checked['issues']:
                errors=checked['issues']
                for key,claim in judgement.get('requirements',{}).items():
                    if isinstance(claim,dict) and claim.get('status') in ('met','failed') and not claim.get('evidence'):
                        errors.append(f'{key}: status={claim.get("status")}但没有有效引用。met/failed必须引用实际原文片段编号；若只是未提及、没有证据，必须unknown且编号0，不能failed。')
                if prompt_tag=='baseline':
                    errors.append(f'输入实际只有 {len(text.splitlines())} 行；start_line/end_line必须引用输入已有编号。unknown时编号0，match=null，strength=0。known时strength必须1至4。')
                errors.append('上次输出：'+json.dumps(judgement,ensure_ascii=False))
                continue
            write_json(path,judgement)
            return judgement
        except AccountBlocked:
            raise
        except Exception as exc:
            errors=[type(exc).__name__+': '+str(exc)[:400]]
            time.sleep(1+attempt)
    write_json(path.with_suffix('.error.json'),
               {'errors':[e for e in (errors or []) if not e.startswith('上次输出：')],'last_judgement':judgement})
    raise ValueError('Evidence extraction failed validation: '+str([e for e in (errors or []) if not e.startswith('上次输出：')]))


def cached_evidence(path,strict=False):
    if path.exists():
        return read(path)
    error=path.with_suffix('.error.json')
    if strict or not error.exists():
        raise ValueError('Missing validated evidence')
    return {'claims':{},'requirements':{},'reason':'证据抽取失败，待复核。',
            'extraction_error':read(error)['errors']}


def collect(rows,jobs,prompt_tag,workers,run_name):
    ensure_extractor_identity(prompt_tag)
    ledger_path=OUT/f'{run_name}_ledger.json'
    final=run_name.startswith('final_')
    ledger=read(ledger_path) if ledger_path.exists() else {}
    if final:
        verify_artifact_ledger(ledger)
    used={r['job_id'] for r in rows}
    rubrics={}
    with ThreadPoolExecutor(max_workers=min(workers,12)) as pool:
        pending={pool.submit(get_rubric,jobs[jid],prompt_tag):jid for jid in used}
        for future in as_completed(pending):
            rubrics[pending[future]]=future.result()
    print(f'{run_name}: {len(rubrics)} rubrics ready',flush=True)
    def work(row,stage):
        text=get_text(row['resume_id'],stage)
        job=jobs[row['job_id']]; rubric=rubrics[row['job_id']]
        path=evidence_path(job,rubric,text,stage,prompt_tag)
        cached=path.exists()
        get_evidence(job,rubric,text,stage,prompt_tag)
        rp=rubric_path(job,prompt_tag)
        artifacts={str(p.relative_to(OUT)):sha(p.read_text(encoding='utf-8')) for p in (path,rp)}
        return artifacts,cached
    failures=[]; completed=0; cached_calls=0; started=time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(work,r,s):(r['pair_id'],s) for r in rows for s in ('precontact','full_resume')}
        for future in as_completed(pending):
            pid,stage=pending[future]
            try:
                artifacts,cached=future.result(); completed+=1; cached_calls+=cached
                if final:
                    ledger.update(artifacts)
                    write_json(ledger_path,ledger)
            except AccountBlocked:
                for queued in pending:
                    queued.cancel()
                write_json(OUT/f'{run_name}_progress.json',
                           {'run':run_name,'prompt_tag':prompt_tag,'status':'blocked_account_arrearage',
                            'expected_calls':2*len(rows),'completed_calls':completed,'failures':failures,
                            'cached_calls':cached_calls,'seconds':round(time.time()-started)})
                raise
            except Exception as exc:
                failures.append({'pair_id':pid,'stage':stage,'error':str(exc)[:300]})
            report={'run':run_name,'prompt_tag':prompt_tag,'expected_calls':2*len(rows),'completed_calls':completed,
                    'failures':failures,'cached_calls':cached_calls,'fresh_stage_extractions':completed-cached_calls,
                    'fine_evaluation_policy':'all_rows_offline_diagnostic_not_actual_pipeline_cost',
                    'seconds':round(time.time()-started),'status':'running'}
            if (completed+len(failures))%50==0 or completed+len(failures)==len(pending):
                write_json(OUT/f'{run_name}_progress.json',report)
                print(json.dumps({**report,'failures':len(failures)}),flush=True)
    report['status']='complete' if not failures else 'incomplete'
    write_json(OUT/f'{run_name}_progress.json',report)
    if failures and final:
        raise RuntimeError(f'{run_name}: {len(failures)} calls need retry; cached success retained')
    return rubrics


def verify_artifact_ledger(ledger):
    for relative,expected in ledger.items():
        path=OUT/relative
        if not path.is_file() or sha(path.read_text(encoding='utf-8'))!=expected:
            raise ValueError(f'Completed test artifact missing or changed: {relative}')


_VALIDATED_COMPONENTS={}


def reweight_assessment(rubric,assessment,weights,prior):
    allocated=criterion_weights(rubric['criteria'],weights)
    total=known=0.0
    for key,weight in allocated.items():
        value=assessment['breakdown'][key]
        observed=value['status']=='known'
        total+=weight*(value['match'] if observed else prior)/100
        if observed:
            known+=weight
    return (round(total,1) if known else None,round(known,1),assessment['threshold_eligible'])


def compact(rows,jobs,prompt_tag,weights,prior,strict=False):
    ensure_extractor_identity(prompt_tag)
    texts={}
    rubrics={jid:read(rubric_path(jobs[jid],prompt_tag)) for jid in {r['job_id'] for r in rows}}
    result=[]
    config={'coarse_coverage':0,'fine_coverage':0}
    for row in rows:
        values=[]
        for stage in ('precontact','full_resume'):
            key=(row['resume_id'],stage)
            if key not in texts:
                texts[key]=get_text(*key)
            text=texts[key]; rubric=rubrics[row['job_id']]
            path=evidence_path(jobs[row['job_id']],rubric,text,stage,prompt_tag)
            artifact=path if path.exists() else path.with_suffix('.error.json')
            if strict and not path.exists():
                raise ValueError('Missing validated final evidence')
            stamp=artifact.stat()
            cache_key=(str(artifact),stamp.st_mtime_ns,stamp.st_size)
            if cache_key not in _VALIDATED_COMPONENTS:
                judgement=cached_evidence(path,strict=strict)
                scored=score_generic(rubric,text,judgement,stage,'partial' if stage=='precontact' else 'complete',50,config=config)
                minimal={'breakdown':{k:{'status':v['status'],'match':v['match']} for k,v in scored['breakdown'].items()},
                         'threshold_eligible':scored['threshold_eligible'],'issues':bool(scored['issues'])}
                _VALIDATED_COMPONENTS[cache_key]=(minimal,bool(judgement.get('extraction_error')))
            scored,technical=_VALIDATED_COMPONENTS[cache_key]
            if strict and scored.get('issues'):
                raise ValueError('Final evidence failed scoring validation')
            values.append((*reweight_assessment(rubric,scored,weights,prior),technical))
        result.append(values)
    return result


def predictions(compacted,config):
    coarse=[]; fine=[]; scores=[]
    for c,f in compacted:
        coarse.append(c[2] and c[1]>=config['coarse_coverage'] and c[0] is not None and c[0]>=config['coarse_threshold'])
        fine.append(f[2] and f[1]>=config['fine_coverage'] and f[0] is not None and f[0]>=config['fine_threshold'])
        scores.append(f[0])
    return coarse,fine,scores


def grid(rows,jobs,prompt_tag):
    if any(r['split']=='test' for r in rows):
        raise ValueError('Cannot tune using test rows')
    train_ids=[i for i,r in enumerate(rows) if r['split']=='train']
    val_ids=[i for i,r in enumerate(rows) if r['split']=='validation']
    trials=[]
    weight_priors = itertools.product(
        [{'core':60,'skill':30,'bonus':10},{'core':55,'skill':35,'bonus':10},{'core':50,'skill':40,'bonus':10}],
        [25,35,45])
    if prompt_tag in REVIEW_TAGS:
        # User requested a model switch, preserving the existing scoring settings.
        weight_priors = [(BASE['weights'], BASE['unknown_prior'])]
    for weights,prior in weight_priors:
        evidence=compact(rows,jobs,prompt_tag,weights,prior)
        settings = itertools.product([20,30,40],[60,70,80],[45,50,55])
        if prompt_tag in REVIEW_TAGS:
            settings = [(BASE['coarse_coverage'], BASE['fine_coverage'], BASE['coarse_threshold'])]
        for cc,fc,threshold in settings:
            config={'weights':weights,'unknown_prior':prior,'coarse_coverage':cc,'fine_coverage':fc,
                    'coarse_threshold':threshold,'fine_threshold':threshold+25,'prompt_tag':prompt_tag}
            c,f,s=predictions(evidence,config)
            subset=lambda ids:metrics([rows[i] for i in ids],[c[i] for i in ids],[f[i] for i in ids],[s[i] for i in ids],
                                      [evidence[i][0][3] or evidence[i][1][3] for i in ids])
            trials.append({'config':config,'train':subset(train_ids),
                           'validation':subset(val_ids) if val_ids else None})
        print(f'grid {prompt_tag}: {weights}, unknown={prior}',flush=True)
    def ordering(trial):
        m=trial['validation'] or trial['train']
        violations=sum(max(0,b-(m[g][k] or 0)) for g,k,b in
            [('coarse','recall',.9),('coarse','precision',.7),('fine','precision',.95),('pipeline','recall',.85)])
        return (meets(m), -violations if not meets(m) else 0,m['weighted_75_25'] or 0,
                -m['fine_calls'],-abs(trial['config']['coarse_threshold']-50))
    trials.sort(key=ordering,reverse=True)
    write_json(OUT/f'grid_{prompt_tag}.json',{'trials':trials,'best':trials[0],
               'implementation_hashes':implementation_hashes(),
               'development_labels_sha256':sha((OUT/'development_labels.json').read_text(encoding='utf-8'))})
    return trials[0]


def report_rows(rows,jobs,config,name):
    tag=config['prompt_tag']
    strict=name.startswith('final_')
    values=compact(rows,jobs,tag,config['weights'],config['unknown_prior'],strict=strict)
    coarse,fine,scores=predictions(values,config)
    technical=[c[3] or f[3] for c,f in values]
    result=metrics(rows,coarse,fine,scores,technical)
    details=[]
    grouped=defaultdict(list)
    rubrics={jid:read(rubric_path(jobs[jid],tag)) for jid in {r['job_id'] for r in rows}}
    for i,(row,c,f,s) in enumerate(zip(rows,coarse,fine,scores)):
        explanations={}
        for stage in ('precontact','full_resume'):
            judgement=cached_evidence(evidence_path(jobs[row['job_id']],rubrics[row['job_id']],
                                        get_text(row['resume_id'],stage),stage,tag),strict=strict)
            explanations[stage]=judgement.get('reason','')
        details.append({**row,'predicted_label_3':2 if c and f else 1 if c else 0,
                        'predicted_coarse_pass':c,'predicted_fine_pass':f,
                        'coarse_score':values[i][0][0],'fine_score':s,'matching_reasons':explanations,
                        'technical_review_required':technical[i]})
        grouped[row['job_id']].append(i)
    job_metrics={jid:metrics([rows[i] for i in ids],[coarse[i] for i in ids],[fine[i] for i in ids],[scores[i] for i in ids],
                            [technical[i] for i in ids])
                 for jid,ids in grouped.items()}
    macro={}
    for group,key in [('coarse','recall'),('coarse','precision'),('fine','precision'),('pipeline','recall')]:
        defined=[m[group][key] for m in job_metrics.values() if m[group][key] is not None]
        macro[f'{group}_{key}']=statistics.mean(defined) if defined else None
    ranking=sorted((i for i in range(len(rows)) if coarse[i]),
                   key=lambda i:-(values[i][0][0] if values[i][0][0] is not None else -1))
    top={str(k):sum(rows[i]['label_3']==2 for i in ranking[:k])/min(k,len(ranking)) if ranking else None
         for k in (10,20)}
    per_job_top={}
    for jid,ids in grouped.items():
        ordered=sorted((i for i in ids if coarse[i]),key=lambda i:-(values[i][0][0] if values[i][0][0] is not None else -1))
        per_job_top[jid]={str(k):sum(rows[i]['label_3']==2 for i in ordered[:k])/min(k,len(ordered)) if ordered else None
                         for k in (10,20)}
    distribution={}
    for label in (0,1,2):
        observed=[s for r,s in zip(rows,scores) if r['label_3']==label and s is not None]
        distribution[str(label)]={'count':len(observed),'mean':statistics.mean(observed) if observed else None,
                                  'median':statistics.median(observed) if observed else None}
    tier_scores=defaultdict(list)
    for row,value in zip(rows,scores):
        tier=row.get('tier')
        if tier is None:
            tier=('silver_hard_negative' if row.get('hard_negative') else 'silver_ordinary_negative') if row['label_3']==0 else f"label_{row['label_3']}"
        if value is not None:
            tier_scores[tier].append(value)
    tiers={tier:{'count':len(values),'mean':statistics.mean(values),'median':statistics.median(values),
                 'min':min(values),'max':max(values)} for tier,values in tier_scores.items()}
    payload={'name':name,'status':'complete','config':config,'metrics':result,'meets_targets':meets(result),
             'macro':macro,'per_job':job_metrics,'topk_qualified_fraction':top,
             'per_job_topk_qualified_fraction':per_job_top,'fine_score_by_label':distribution,
             'fine_score_by_tier':tiers,
             'topk_population':'coarse_passed_candidates_ranked_by_coarse_score',
             'label_source':'historical_frozen_labels' if name=='final_history' else 'llm_silver','rows':details}
    write_json(OUT/f'{name}.json',payload)
    return payload


def history_full(case):
    from recruitment_app.local_eval import redact_contacts
    original=redact_contacts(case['text'])
    recovered=OUT/f"history/recovered/H_{case['id']}.json"
    if not recovered.exists():
        return original
    item=read(recovered)
    if item['original_extraction_sha256']!=sha(original) or item['sha256']!=sha(item['full']):
        raise ValueError('Recovered history source changed')
    return item['full']


def prepare_history(workers):
    from recruitment_app.local_eval import load_local_cases, redact_contacts
    from .generate_short_resumes import SYSTEM as SUMMARY_PROMPT, validate as validate_summary
    from recruitment_app.llm import JobModel
    cases=load_local_cases(ROOT/'Samples_for_optimization')
    assert len(cases)==120
    def work(case):
        cid='H_'+case['id']
        full=history_full(case)
        path=OUT/f'history/texts/{cid}.json'
        if path.exists():
            item=read(path)
            if item['source_sha256']==sha(full):
                validate_summary(item['short'])
                return cid,item
        model=JobModel.from_environment(); model.model='qwen-plus'
        correction=''; previous=''; overlong=False
        diagnostic=OUT/f'history/diagnostics/{cid}.json'
        attempts=0 if diagnostic.exists() and read(diagnostic).get('attempt')==8 else 8
        for attempt in range(attempts):
            try:
                user=previous if overlong else '<resume>\n'+full+'\n</resume>'+previous
                result=model._ask(SUMMARY_PROMPT+correction,user)
                short=result.get('text_zh')
                previous='\n上次草稿：'+str(short)
                overlong=isinstance(short,str) and len(''.join(short.split()))>200
                size=validate_summary(short)
                item={'id':cid,'full':full,'short':short,'source_sha256':sha(full),'short_sha256':sha(short),
                      'model':model.model,'chars':size}
                write_json(path,item)
                return cid,item
            except ValueError as exc:
                correction='\n上次校验失败：'+str(exc)
                correction+=('。删除至少一句次要事实，将草稿缩短到130至170字符。' if overlong else
                             '。增加至少50个中文字符，从原文补充两项事实，目标180字符，不可编造。')
                write_json(OUT/f'history/diagnostics/{cid}.json',
                           {'error':str(exc),'last_draft':previous,'source_chars':len(full),'attempt':attempt+1})
        # Sparse historical records can cause repeated paraphrase/length drift.
        # Let the API select exact source fragments instead; local code only joins them.
        fragments=[s.strip() for s in re.split(r'(?<=[。；;])|\r?\n',full) if s.strip()]
        fragments=[s for s in fragments if 8<=len(s)<=180 and not re.search(
            r'姓名|性别|出生|地址|电话|邮箱|微信|QQ|籍贯|期望薪资|PHONE|EMAIL',s,re.I)]
        selected=model._ask(
            '只返回JSON {"ids":[整数编号]}。从编号简历原文片段中选择职业职责、项目、技能、学历事实，按信息价值排序。'
            '没有目标岗位，不判断匹配程度。至少选择6个可用片段（不足6个则全部）。不要身份联系方式，不改写或编造事实。',
            json.dumps({str(i):s for i,s in enumerate(fragments,1)},ensure_ascii=False))
        pieces=[]
        for index in selected.get('ids',[]):
            if type(index) is int and 1<=index<=len(fragments):
                piece=fragments[index-1]
                if piece not in pieces and len(' '.join(pieces+[piece]))<=200:
                    pieces.append(piece)
                if len(''.join(pieces))>=100:
                    break
        short=' '.join(pieces)
        size=validate_summary(short)
        item={'id':cid,'full':full,'short':short,'source_sha256':sha(full),'short_sha256':sha(short),
              'model':model.model,'chars':size,'method':'llm_selected_exact_source_fragments'}
        write_json(path,item)
        return cid,item
    texts={}
    failures=[]
    with ThreadPoolExecutor(max_workers=min(workers,32)) as pool:
        pending={pool.submit(work,case):case['id'] for case in cases}
        for future in as_completed(pending):
            try:
                cid,item=future.result()
                texts[cid]=item
            except Exception as exc:
                failures.append({'id':pending[future],'error':str(exc)[:300]})
    write_json(OUT/'history/preparation_status.json',
               {'expected':len(cases),'completed':len(texts),'failures':failures})
    if failures:
        raise ValueError('Historical inputs incomplete; see history/preparation_status.json')
    rows=[]
    for case in cases:
        label=2 if case['expected_fine']=='pass' else 1 if case['expected_coarse']=='pass' else 0
        cid='H_'+case['id']
        rows.append({'pair_id':cid+'_ONTOLOGY_ORIGINAL','resume_id':cid,'job_id':'ONTOLOGY_ORIGINAL',
                     'split':'historical_regression','label_3':label,'score':None,'tier':case['tier'],
                     'coarse_labeled':case['expected_coarse'] is not None,
                     'original_expected_coarse':case['expected_coarse'],'original_expected_fine':case['expected_fine'],
                     'label_source':'historical_frozen_labels'})
    manifest={'rows':rows,'text_hashes':{cid:digest(item) for cid,item in texts.items()},
              'job_sha256':sha((ROOT/'Samples_for_optimization/recruitment_request.txt').read_text(encoding='utf-8'))}
    path=OUT/'history/manifest.json'
    if path.exists() and read(path)!=manifest:
        raise ValueError('Historical snapshot changed')
    write_json(path,manifest)
    print('Historical 120 summaries and labels prepared.',flush=True)


def freeze_best(prompt_tags):
    if (OUT/'test_opened.json').exists():
        raise ValueError('Final test already opened; cannot select a new candidate')
    assert_inputs()
    trials=[]
    for tag in prompt_tags:
        grid_result=read(OUT/f'grid_{tag}.json')
        if grid_result.get('implementation_hashes')!=implementation_hashes():
            raise ValueError('Validation grid implementation is stale; reaggregate cached evidence')
        if grid_result.get('development_labels_sha256')!=sha((OUT/'development_labels.json').read_text(encoding='utf-8')):
            raise ValueError('Validation grid label version is stale')
        trials.append(grid_result['best'])
    def key(t):
        m=t['validation']
        violation=sum(max(0,b-(m[g][k] or 0)) for g,k,b in
            [('coarse','recall',.9),('coarse','precision',.7),('fine','precision',.95),('pipeline','recall',.85)])
        return (meets(m),-violation,m['weighted_75_25'] or 0,-m['fine_calls'])
    best=max(trials,key=key)
    frozen={'config':best['config'],'data_hash':all_data_hash(),'implementation_hashes':implementation_hashes(),
            'validation':best['validation'],'train':best['train'],'candidate_tags':prompt_tags,
            'validation_passed':meets(best['validation'])}
    path=OUT/'frozen_config.json'
    if path.exists() and read(path)!=frozen:
        raise ValueError('Frozen configuration already exists')
    write_json(path,frozen)
    print(json.dumps(frozen['config']),flush=True)


def final_test(workers):
    assert_inputs()
    frozen=read(OUT/'frozen_config.json')
    config=frozen['config']
    authorize_test(OUT,config,all_data_hash())
    if (OUT/'final_completion_seal.json').exists():
        verify_artifact_ledger(read(OUT/'final_completion_seal.json'))
        for ledger_path in OUT.glob('final_*_ledger.json'):
            verify_artifact_ledger(read(ledger_path))
        print('Final test already complete; verified saved artifacts without API calls.',flush=True)
        return
    rows=[r for r in read(CORPUS/'pair_labels_llm.json')['labels'] if r['split']=='test']
    jobs={j['id']:j['text'] for j in read(CORPUS/'jobs.json')['jobs']}
    ontology=read(OUT/'ontology_truth.json')
    jobs['ONTOLOGY_ORIGINAL']=ontology['job']
    history=read(OUT/'history/manifest.json')
    for cid,expected in history['text_hashes'].items():
        if digest(read(OUT/f'history/texts/{cid}.json'))!=expected:
            raise ValueError('Historical input changed after freeze')
    suites=[('final_cross_job',rows),('final_ontology',ontology['labels']),('final_history',history['rows'])]
    reports={}
    for name,suite in suites:
        # Resume only missing technical work under the exact frozen identity.
        collect(suite,jobs,config['prompt_tag'],workers,name)
        reports[name]=report_rows(suite,jobs,config,name)
    hist=reports['final_history']
    unchanged=hist['metrics']['pipeline']['fp']==0 and hist['metrics']['pipeline']['fn']==0
    unrelated=[r for r in hist['rows'] if r['tier']=='unrelated']
    regression_ok=unchanged and all(not r['predicted_coarse_pass'] for r in unrelated)
    approved=all(reports[name]['meets_targets'] for name in ('final_cross_job','final_ontology')) and regression_ok
    write_json(OUT/'final_summary.json',{'status':'complete','approved_for_default':approved,
        'config':config,'historical_regression_passed':regression_ok,
        'suites':{name:{'metrics':r['metrics'],'meets_targets':r['meets_targets'],'macro':r['macro'],
                       'topk_qualified_fraction':r['topk_qualified_fraction']} for name,r in reports.items()},
        'label_source':'LLM silver for new data; historical labels for regression',
        'online_guarantee':False})
    report_paths=[OUT/'final_summary.json']+[OUT/f'{name}.json' for name,_ in suites]
    write_json(OUT/'final_completion_seal.json',
               {str(p.relative_to(OUT)):sha(p.read_text(encoding='utf-8')) for p in report_paths})
    print(json.dumps({'final_complete':True,'approved_for_default':approved}),flush=True)


def development(prompt_tag,workers,limit=None,aggregate_only=False):
    rows,jobs=load_development(limit)
    name=f'pilot_{prompt_tag}' if limit else f'development_{prompt_tag}'
    if not aggregate_only:
        collect(rows,jobs,prompt_tag,workers,name)
    report_rows(rows,jobs,{**BASE,'prompt_tag':prompt_tag},name+'_baseline')
    if not limit:
        grid(rows,jobs,prompt_tag)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['development','aggregate','prepare-history','freeze','final-test'])
    parser.add_argument('--prompt-tag',default='baseline')
    parser.add_argument('--workers',type=int,default=64)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--tags',default='baseline')
    args=parser.parse_args()
    if args.action in ('development','aggregate'):
        development(args.prompt_tag,args.workers,args.limit,aggregate_only=args.action=='aggregate')
    elif args.action=='prepare-history':
        prepare_history(args.workers)
    elif args.action=='freeze':
        freeze_best(args.tags.split(','))
    else:
        final_test(args.workers)
