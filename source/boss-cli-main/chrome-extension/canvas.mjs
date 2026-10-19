// Fixed, read-only export of canvases inside BOSS's online resume frame.
export async function resumeCanvasPage([action,index,deadline,expectedIdentity]) {
 if(Date.now()>=deadline) throw Error('Canvas 读取已过期');
 if(location.origin!=='https://www.zhipin.com' || !location.pathname.startsWith('/web/frame/c-resume')) return null;
 if(!['inspect','image','diagnostic'].includes(action)) throw Error('不支持的 Canvas 操作');
 const sample=async()=>{
   const canvases=Array.from(document.querySelectorAll('canvas')).filter(c=>c.getClientRects().length);
   if(canvases.length>30) throw Error('Canvas 页数超过安全上限');
   const metrics=canvases.map((c,i)=>{
     const rect=c.getBoundingClientRect();
     return {index:i,width:c.width,height:c.height,css_width:rect.width,css_height:rect.height,
       x:rect.x+scrollX,y:rect.y+scrollY};
   });
   let drawn=canvases.length>0;
   const pixelStats=[];
   const chunks=[new TextEncoder().encode(location.href+'|'+(document.body?.innerText||'').slice(0,20000)+'|'+JSON.stringify(metrics))];
   for(const canvas of canvases){
     if(canvas.width<400||canvas.height<400||canvas.width*canvas.height>20000000){
       drawn=false;pixelStats.push({dark:0,light:0,sampled:false});continue;
     }
     const scratch=document.createElement('canvas');scratch.width=128;scratch.height=128;
     const ctx=scratch.getContext('2d',{willReadFrequently:true});
     ctx.drawImage(canvas,0,0,128,128);
     const pixels=ctx.getImageData(0,0,128,128).data;
     let dark=0,light=0;
     for(let i=0;i<pixels.length;i+=4){
       if(pixels[i+3]<32) continue;
       const tone=(pixels[i]+pixels[i+1]+pixels[i+2])/3;
       if(tone<140) dark++;
       if(tone>200) light++;
     }
     if(dark<5||light<100) drawn=false;
     pixelStats.push({dark,light,sampled:true});
     chunks.push(new Uint8Array(pixels));
   }
   const bytes=new Uint8Array(chunks.reduce((sum,c)=>sum+c.length,0));
   let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
   const hash=await crypto.subtle.digest('SHA-256',bytes);
   const identity=Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('');
   return {canvases,metrics,drawn,identity,pixelStats};
 };
 let current=await sample();
 if(action==='inspect') {
   const until=Math.min(deadline-3000,Date.now()+15000);
   let last=current.drawn?current.identity:null,stable=current.drawn?1:0;
   while(Date.now()<until && stable<3){
     await new Promise(resolve=>setTimeout(resolve,250));
     current=await sample();
     stable=current.drawn?(current.identity===last?stable+1:1):0;
     last=current.drawn?current.identity:null;
   }
   return {frame_url:location.origin+location.pathname,document_height:document.documentElement.scrollHeight,
     viewport_height:innerHeight,canvas_count:current.canvases.length,canvases:current.metrics,
     initialized:current.drawn&&stable>=3,identity:current.drawn&&stable>=3?current.identity:null,
     pixel_stats:current.pixelStats,stable_count:stable};
 }
 if(action==='diagnostic') {
   if(!Number.isInteger(index)||index<0||index>=current.canvases.length) throw Error('Canvas 页码无效');
   const item=current.metrics[index];
   if(item.width<100||item.height<100||item.width*item.height>20000000) throw Error('Canvas 尺寸不可信');
   const data=current.canvases[index].toDataURL('image/png');
   if(!data.startsWith('data:image/png;base64,')||data.length>20000000) throw Error('Canvas 图片不可导出');
   const after=await sample();
   return {frame_url:location.origin+location.pathname,canvas_count:current.canvases.length,
     canvas:item,pixel_stats:current.pixelStats[index],unstable:after.identity!==current.identity,
     png:data.slice('data:image/png;base64,'.length)};
 }
 if(!current.drawn||!expectedIdentity||current.identity!==expectedIdentity) throw Error('Canvas 内容或简历身份已变化');
 if(!Number.isInteger(index)||index<0||index>=current.canvases.length) throw Error('Canvas 页码无效');
 const item=current.metrics[index];
 const data=current.canvases[index].toDataURL('image/png');
 if(!data.startsWith('data:image/png;base64,')||data.length>20000000) throw Error('Canvas 图片不可导出');
 const after=await sample();
 if(after.identity!==current.identity||!after.drawn) throw Error('Canvas 导出过程中内容变化');
 return {frame_url:location.origin+location.pathname,document_height:document.documentElement.scrollHeight,
   viewport_height:innerHeight,canvas_count:current.canvases.length,canvas:item,identity:current.identity,
   png:data.slice('data:image/png;base64,'.length)};
}
