"""Immutable evidence-v1 extractor; new experiments use new modules/tags."""
import copy
import json
import re
from recruitment_app.generic_model import GenericJobModel, RUBRIC_PROMPT, EVIDENCE_PROMPT
from recruitment_app.core import validate_rubric


def source_segments(text):
    spans=[]
    start=0
    for match in re.finditer(r'[。；;\n]+',text):
        end=match.end()
        if text[start:end].strip():
            spans.append((start,end))
        start=end
    if text[start:].strip():
        spans.append((start,len(text)))
    return spans


class OptimizedModel(GenericJobModel):
    variant='evidence-v1'

    def rubric(self,job):
        if self.variant!='evidence-v1':
            raise ValueError('Unregistered immutable prompt version')
        spans=source_segments(job)
        prompt=RUBRIC_PROMPT.replace('jd_quote','jd_quote_id')
        prompt+=(
            '\n本版本jd_quote_id必须是输入片段的整数编号，禁止自行输出引用文字。'
            '单项取最相关的一段；不要通过拼接增加要求。'
            'criteria覆盖实际核心产出、可迁移技能和优先条件，避免一个细节重复计分。'
            'requirements只列明确、必要的准入条件。接受应届、经验不限、无需经验不是硬条件，绝对不要列入。'
            '任务职责作为评分项，不能将所有职责重复设成逐项一票否决的准入条件。'
            '“或”表示满足任意一个，不可拆成多个都必须满足的硬条件。'
        )
        payload={'job':job,'segments':{str(i):job[a:b] for i,(a,b) in enumerate(spans,1)}}
        result=self._ask(prompt,json.dumps(payload,ensure_ascii=False))
        for group in ('criteria','requirements'):
            for item in result.get(group,[]):
                index=item.pop('jd_quote_id',None)
                if type(index) is not int or not 1<=index<=len(spans):
                    raise ValueError('Invalid job source segment')
                a,b=spans[index-1]
                item['jd_quote']=job[a:b]
        result=validate_rubric(job,result)
        for item in result['criteria']+result['requirements']:
            item['name']=item['jd_quote']
        return result

    def evidence_generic(self,rubric,text,correction=None):
        if not isinstance(text,str) or not text.strip() or len(text)>30000:
            raise ValueError('Invalid resume length')
        spans=source_segments(text)
        payload={'rubric':rubric,'resume_segments':{str(i):text[a:b] for i,(a,b) in enumerate(spans,1)}}
        if correction:
            payload['validation_errors']=correction
        prompt=EVIDENCE_PROMPT+(
            '\n本版本start_line/end_line指输入resume_segments编号，不是自行推断的排版行号。'
            '只使用实际存在的整数编号。known时strength必须是1/2/3/4；明确不匹配用match=0但strength仍需1至4。'
            'unknown严格返回match=null,strength=0,start_line=0,end_line=0。'
            'requirements的unknown也必须start_line=0,end_line=0。'
            '逐项检查实际工作对象、采取动作、成果与岗位需求。跨行业但工作任务相同可充分匹配；'
            '仅同名术语、服务对象相同或工具相同，工作任务不同，应弱相关。'
            '明确从事完全不同的工作可以引用实际经历作为弱相关证据，不能虚构从未从事某工作。'
            '合理基础技能可由直接完成相应任务证明，不强制简历逐字列出岗位词汇。'
            '只抽取事实证据，不输出最终通过结论。'
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
