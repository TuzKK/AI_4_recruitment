"""Bounded exact spans for punctuation-free translated resumes."""
import copy
import json
from .screening_prompt_v2 import AtomicJobModel
from .screening_prompt_variants import source_segments
from recruitment_app.generic_model import EVIDENCE_PROMPT


def bounded_segments(text):
    result=[]
    for start,end in source_segments(text):
        while end-start>180:
            cut=text.rfind(' ',start+80,start+180)
            cut=cut+1 if cut>=0 else start+180
            result.append((start,cut))
            start=cut
        if text[start:end].strip():
            result.append((start,end))
    return result


class BoundedJobModel(AtomicJobModel):
    variant='evidence-v3'

    def evidence_generic(self,rubric,text,correction=None):
        if not isinstance(text,str) or not text.strip() or len(text)>30000:
            raise ValueError('Invalid resume length')
        spans=bounded_segments(text)
        payload={'rubric':rubric,'resume_segments':{str(i):text[a:b] for i,(a,b) in enumerate(spans,1)}}
        if correction:
            payload['validation_errors']=correction
        prompt=EVIDENCE_PROMPT+(
            '\nstart_line/end_line只能是输入resume_segments已有的整数编号，不是排版行号。'
            'known时match取0/25/50/75/100，strength为1至4；match=0也不能strength=0。'
            'unknown必须match=null,strength=0,start_line=0,end_line=0；requirements未知也用0编号。'
            '按工作对象、实际动作和产出判断：不同领域但同类任务可以迁移，只有术语或工具相同不能证明职责胜任。'
            '直接完成相关任务可证明基础技能，不要求重复写出关键词；不能由SQL经验臆测Python经验。'
            '材料中没有的信息保持unknown，不编造缺失经历或不具备能力的事实。'
            '只输出事实证据与简短理由，最终分数和通过结论由规则计算。'
        )
        result=copy.deepcopy(self._ask(prompt,json.dumps(payload,ensure_ascii=False)))
        for group in ('claims','requirements'):
            values=result.get(group,{})
            if not isinstance(values,dict):
                continue
            for claim in values.values():
                if not isinstance(claim,dict):
                    continue
                start,end=claim.get('start_line'),claim.get('end_line')
                claim['evidence']=''
                if claim.get('status')!='unknown' and type(start) is int and type(end) is int and 1<=start<=end<=len(spans):
                    claim['evidence']=text[spans[start-1][0]:spans[end-1][1]].strip()
        return result
