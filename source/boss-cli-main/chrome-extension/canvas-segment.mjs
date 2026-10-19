import {capturePage} from './capture.mjs';
import {resumeCanvasPage} from './canvas.mjs';

// Export one rendered viewport after scrolling the already identified resume host.
// Return to the original top bitmap to rule out a candidate switch during the step.
export async function captureCanvasSegment(chrome,tabId,session,binding,top,deadline) {
 if(!Number.isInteger(top)||top<0||top>Math.max(0,session.initial.total-session.initial.height))
   throw Error('简历滚动位置无效');
 if(session.tabId!==tabId||!binding.identity||!binding.documentId) throw Error('简历截图会话未绑定');
 const scroll=async(position,limit=deadline)=>{
   const rows=await chrome.scripting.executeScript({target:{tabId,documentIds:[session.documentId]},
     func:capturePage,args:['step',position,limit]});
   const metrics=rows[0]?.result;
   if(!metrics||metrics.frame_url!==session.frameUrl||
      Math.abs(metrics.top-position)>2||metrics.height!==session.initial.height||metrics.total!==session.initial.total)
     throw Error('简历滚动布局已变化');
   return metrics;
 };
 const canvas=async(action,identity=null,limit=deadline)=>{
   const frames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:resumeCanvasPage,
     args:[[action,action==='image'?0:null,limit,identity]]});
   const matches=frames.filter(f=>f.result);
   if(matches.length!==1||matches[0].documentId!==binding.documentId)
     throw Error('在线简历 Canvas 文档已变化');
   return matches[0].result;
 };
 const baseline=async(limit=deadline)=>{
   const state=await canvas('inspect',null,limit);
   if(!state.initialized||state.identity!==binding.identity||state.canvas_count!==1)
     throw Error('简历顶部画布身份已变化');
 };
 let restoreNeeded=false,output,error;
 try {
   restoreNeeded=true;
   await scroll(0);
   await baseline();
   const metrics=await scroll(top);
   const state=await canvas('inspect');
   if(!state.initialized||state.canvas_count!==1) throw Error('滚动后的简历画布未稳定');
   const image=await canvas('image',state.identity);
   if(image.identity!==state.identity||image.canvas_count!==1) throw Error('简历画布导出时已变化');
   output={top:metrics.top,height:metrics.height,total:metrics.total,
     canvas:image.canvas,png:image.png,identity:state.identity};
 } catch(e) {error=e;}
 if(restoreNeeded) {
   try {await scroll(0,Math.max(deadline,Date.now()+4000));await baseline(Math.max(deadline,Date.now()+4000));}
   catch(e) {error=Error('简历滚动未能恢复并核实顶部画布');}
 }
 if(error) throw error;
 return output;
}
