import time
from analyzer.position_analyzer import analyze_position
from utils.llm_client import llm
start=time.monotonic()
try:
    result=analyze_position('软件工程师','诊断用示例岗位，仅验证模型输出，不创建数据库记录或招聘任务。')
    valid=bool(result.jd.title and result.keywords.primary_keywords)
    print({'model':llm.model,'analysis_valid':valid,'seconds':round(time.monotonic()-start,2),'keyword_count':len(result.keywords.primary_keywords)},flush=True)
    if not valid: raise SystemExit(1)
except Exception as exc:
    print({'error_type':type(exc).__name__,'seconds':round(time.monotonic()-start,2)},flush=True)
    raise SystemExit(1)
