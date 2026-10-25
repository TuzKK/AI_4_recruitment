const $=id=>document.getElementById(id);
const runToken=document.querySelector('meta[name="run-token"]').content;
let current=null,timer=null;
function updateMessageMode(){
  const ai=$('message-mode').value==='llm';
  $('fixed-message').hidden=ai;$('message').required=!ai;$('message').disabled=ai;
  $('ai-message-help').hidden=!ai;
}
$('message-mode').addEventListener('change',updateMessageMode);
updateMessageMode();
const messageStatuses={pending:'待准备',reviewing:'复核中',rewriting:'重写中',approved:'复核通过',rejected:'复核未通过',fixed:'固定消息'};
const endReasons={quota_reached:'已达到本轮联系名额',no_more_candidates:'连续加载后未发现新候选人，尚未达到联系目标',scan_limit:'已达到单轮200人扫描上限，可继续下一轮',waiting_resume:'已联系，等待完整简历',needs_review:'存在发送结果待核查的记录'};
const contactStates={qualified:'待联系',message_rejected:'已跳过',sent_verified:'已联系且精筛通过',waiting_resume:'已联系，等待完整简历',needs_review:'发送待核查',
  greet_pending:'正在打招呼',greet_not_sent:'未发送，可修复后恢复',candidate_unavailable:'候选人已离开当前列表，未发送，继续下一人',greet_verified:'已打招呼',message_pending:'正在发送',fine_done:'精筛未通过',
  coarse_done:'粗筛已完成',insufficient_resume:'简历不完整',resume_too_long:'简历超出长度限制'};
async function call(path,method='GET',body){
  const response=await fetch(path,{method,headers:{'Content-Type':'application/json','X-Run-Token':runToken},body:body?JSON.stringify(body):undefined});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'请求失败');return data;
}
async function refresh(){
  if(!current)return;
  try{const s=await call(`/api/runs/${current}`);
    const body=$('run-rows');body.replaceChildren();
    for(const candidate of s.candidates||[]){
      const tr=document.createElement('tr');
      const scoreWithCoverage=(score,coverage)=>`${score??'—'}${coverage==null?'':`（覆盖${coverage}%）`}`;
      for(const value of [candidate.name,scoreWithCoverage(candidate.coarse_score,candidate.coarse_coverage),scoreWithCoverage(candidate.fine_score,candidate.fine_coverage),
        candidate.decision||'—',[candidate.reason,...(candidate.rule_adjustments||[])].filter(Boolean).join('；')||'—',(candidate.gaps||[]).join('、')||'—',
        candidate.message_text||'—',messageStatuses[candidate.message_status]||'—',
        [contactStates[candidate.contact_state]||candidate.contact_state,candidate.message_reason].filter(Boolean).join('；')||'—']){
        const td=document.createElement('td');td.textContent=String(value);tr.appendChild(td);
      }
      body.appendChild(tr);
    }
    $('run-table').hidden=!(s.candidates||[]).length;
    $('status').textContent=`状态：${s.status==='waiting_resume'?'等待简历（稍后点击恢复）':s.status}\n岗位：${s.title||'分析中'}\n已扫描：${s.scanned}  精筛通过：${s.fine_passed}  等待简历：${s.waiting_resume??0}  资料不足：${s.insufficient}\n已确认打招呼：${s.contacted}/${s.quota}  已使用名额：${s.greetings_used??s.contacted}  待核查：${s.needs_review}${s.error?'\n错误：'+s.error:''}`;
    $('start').disabled=['running','stop_requested','queued'].includes(s.status);
    if(s.end_reason)$('status').textContent+='\n结束原因：'+(endReasons[s.end_reason]||s.end_reason);
    $('stop').disabled=s.status!=='running';
    if(['finished','failed','paused','waiting_resume'].includes(s.status)){clearInterval(timer);timer=null;$('start').disabled=false;$('stop').disabled=true;}
    $('resume').hidden=!['paused','failed','waiting_resume'].includes(s.status);
  }catch(error){$('status').textContent=error.message;clearInterval(timer);timer=null;}
}
$('run-form').addEventListener('submit',async event=>{
  event.preventDefault();$('start').disabled=true;$('status').textContent='正在启动…';
  try{const data=await call('/api/runs','POST',{job:$('job').value,quota:Number($('quota').value),
    message_mode:$('message-mode').value,message:$('message-mode').value==='fixed'?$('message').value:'',
    coarse_threshold:Number($('coarse').value),fine_threshold:Number($('fine').value),
    rate_limits:{request_seconds:Number($('request-seconds').value),greet_seconds:Number($('greet-seconds').value)}});
    current=data.id;localStorage.setItem('lastRun',current);$('stop').disabled=false;await refresh();timer=setInterval(refresh,1500);
  }catch(error){$('status').textContent=error.message;$('start').disabled=false;}
});
$('stop').addEventListener('click',async()=>{if(current){try{await call(`/api/runs/${current}/stop`,'POST',{});await refresh();}catch(error){$('status').textContent=error.message;}}});
$('resume').addEventListener('click',async()=>{if(current){try{await call(`/api/runs/${current}/resume`,'POST',{});$('start').disabled=true;$('stop').disabled=false;$('resume').hidden=true;timer=setInterval(refresh,1500);await refresh();}catch(error){$('status').textContent=error.message;}}});
async function restore(){
  try{
    const active=await call('/api/active-run');
    current=active.id||localStorage.getItem('lastRun');
    if(current){localStorage.setItem('lastRun',current);await refresh();if(['running','stop_requested','queued'].includes(active.status))timer=setInterval(refresh,1500);}
  }catch(error){$('status').textContent=error.message;}
}
restore();
let ratePollBusy=false;
async function refreshRate(){
  if(ratePollBusy)return;
  ratePollBusy=true;
  try{
    const s=await call('/api/connector-status');
    const r=s.rate_limit||{};
    const seconds=Math.max(0,Math.ceil(((r.until||0)-Date.now())/1000));
    $('rate-status').textContent=!s.connected?'BOSS连接器未连接':
      s.rate_limit_version!==1?'请升级连接器以启用统一限速':
      r.state==='cooldown'&&seconds>0?`BOSS限流冷却：剩余${seconds}秒，结束后可恢复任务`:
      r.state==='waiting'&&seconds>0?`限速等待：剩余${seconds}秒（尚未执行下一次请求）`:
      `BOSS限速已启用：请求至少${r.request_seconds||5}秒，打招呼至少${r.greet_seconds||20}秒`;
  }catch{ $('rate-status').textContent='暂时无法读取连接器状态'; }
  finally{ratePollBusy=false;}
}
void refreshRate();setInterval(refreshRate,2000);

let localEvalId=null,localTimer=null;
function renderLocalRows(rows){
  const body=$('local-rows');body.replaceChildren();
  for(const row of rows){
    const tr=document.createElement('tr');
    const fine=row.fine||{},coarse=row.coarse||{};
    for(const value of [row.id,row.tier,coarse.score??'—',fine.score??'—',
      fine.decision||fine.error||'—',[fine.reason,...(fine.rule_adjustments||[])].filter(Boolean).join('；')||'—',(fine.gaps||[]).join('、')||'—']){
      const td=document.createElement('td');td.textContent=String(value);tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  $('local-table').hidden=rows.length===0;
}
async function refreshLocal(){
  if(!localEvalId)return;
  try{
    const state=await call(`/api/local-eval/${localEvalId}`);
    $('local-status').textContent=`状态：${state.status}；已评测：${state.done}/${state.total}`+
      (state.error?`；错误：${state.error}`:'');
    if(state.status==='finished'){
      clearInterval(localTimer);localTimer=null;$('start-local-eval').disabled=false;
      const s=state.summary||{};
      $('local-summary').textContent=`最终放行判断：${s.pipeline_metrics?.correct??0}/${s.pipeline_metrics?.expected??0}；`+
        `粗筛召回率：${((s.coarse_metrics?.recall??0)*100).toFixed(1)}%；`+
        `精筛精确率：${((s.fine_metrics?.precision??0)*100).toFixed(1)}%；`+
        `精筛通过/待复核/拒绝三分类：${s.fine_metrics?.matching_decisions??0}/${s.fine_metrics?.expected??0}；`+
        `层级中位数顺序：${s.tiers?.ordered_medians?'符合':'未符合'}；`+
        `困难负例与无关负例中位差：${s.tiers?.hard_unrelated_margin??'—'} 分；`+
        `探索阈值：粗筛 ${s.suggested_coarse?.threshold??'—'}、精筛 ${s.suggested_fine?.threshold??'—'}`;
      renderLocalRows(state.candidates||[]);
      const report=$('local-report');report.href=`/api/local-eval/${localEvalId}/report`;
      report.download=`local-eval-${localEvalId}.json`;report.hidden=false;
    }else if(state.status==='failed'){
      clearInterval(localTimer);localTimer=null;$('start-local-eval').disabled=false;
    }
  }catch(error){
    $('local-status').textContent=error.message;clearInterval(localTimer);localTimer=null;
    $('start-local-eval').disabled=false;
  }
}
$('load-sample-job').addEventListener('click',async()=>{
  try{const data=await call('/api/sample-job');$('job').value=data.job;
    if(data.recommended_thresholds){$('coarse').value=data.recommended_thresholds.coarse;$('fine').value=data.recommended_thresholds.fine;}}
  catch(error){$('local-status').textContent=error.message;}
});
$('start-local-eval').addEventListener('click',async()=>{
  if(!$('job').value.trim()){$('local-status').textContent='请先填写或载入完整招聘需求';return;}
  $('start-local-eval').disabled=true;$('local-report').hidden=true;renderLocalRows([]);
  $('local-status').textContent='正在启动本地评测…';
  try{
    const data=await call('/api/local-eval','POST',{job:$('job').value,
      coarse_threshold:Number($('coarse').value),fine_threshold:Number($('fine').value)});
    localEvalId=data.id;await refreshLocal();localTimer=setInterval(refreshLocal,1500);
  }catch(error){$('local-status').textContent=error.message;$('start-local-eval').disabled=false;}
});
