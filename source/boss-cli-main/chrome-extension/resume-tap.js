// Runs at document_start in the page's MAIN world. Only observes data the page
// itself parses or draws; it never calls BOSS APIs or changes the return value.
(() => {
  if (location.origin !== 'https://www.zhipin.com' ||
      !/^\/web\/frame\/(recommend|c-resume)(\/|$)/.test(location.pathname)) return;
  const state={details:[],drawnText:[],messages:[],parseCount:0,drawCount:0};
  Object.defineProperty(globalThis,'__bossResumeTap',{value:state,configurable:false});

  const findResume=(root)=>{
    const seen=new WeakSet();
    let visited=0;
    const walk=(value,depth)=>{
      if(!value || typeof value!=='object' || depth>5 || seen.has(value) || ++visited>1000) return null;
      seen.add(value);
      if(value.geekDetailInfo && typeof value.geekDetailInfo==='object') return value.geekDetailInfo;
      if(value.geekBaseInfo || value.geekWorkExpList || value.geekProjExpList || value.geekProjectExpList) return value;
      for(const child of (Array.isArray(value)?value.slice(0,30):Object.values(value).slice(0,50))){
        const found=walk(child,depth+1);
        if(found) return found;
      }
      return null;
    };
    return walk(root,0);
  };
  const originalParse=JSON.parse;
  JSON.parse=function(...args){
    const result=Reflect.apply(originalParse,this,args);
    try {
      state.parseCount++;
      if(typeof args[0]==='string') {
        const resume=findResume(result);
        if(resume) {
          const encoded=JSON.stringify(resume);
          if(encoded && encoded.length<=1000000) {
            state.details.push({at:Date.now(),value:Reflect.apply(originalParse,JSON,[encoded])});
            if(state.details.length>3) state.details.shift();
          }
        }
      }
    } catch { /* Observation must never affect the page's parser. */ }
    return result;
  };

  if(location.pathname.includes('/recommend')) {
    const allowed=new Set(['IFRAME_DONE','WASM_ERROR','WASM_INIT_ERROR','WASM_NO_SUPPORT']);
    globalThis.addEventListener('message',event=>{
      try {
        if(event.origin!==location.origin || !event.data || !allowed.has(event.data.type)) return;
        const frames=document.querySelectorAll('iframe[src*="/web/frame/c-resume"]');
        if(![...frames].some(frame=>frame.contentWindow===event.source)) return;
        const record={type:event.data.type,data:event.data.data||{},at:Date.now()};
        const encoded=JSON.stringify(record);
        if(encoded && encoded.length<=1000000) {
          state.messages.push(Reflect.apply(originalParse,JSON,[encoded]));
          if(state.messages.length>5) state.messages.shift();
        }
      } catch { /* Observation must never affect the page's messages. */ }
    });
  }

  const proto=globalThis.CanvasRenderingContext2D?.prototype;
  if(location.pathname.includes('/c-resume') && proto) {
    for(const method of ['fillText','strokeText']) {
      const original=proto[method];
      if(typeof original!=='function') continue;
      proto[method]=function(...args){
        const result=Reflect.apply(original,this,args);
        try {
          state.drawCount++;
          const canvas=this.canvas;
          if(canvas && canvas.width>=400 && canvas.height>=400 &&
             typeof args[0]==='string' && args[0].length<=400 && state.drawnText.length<10000) {
            state.drawnText.push({text:args[0],x:Number(args[1]),y:Number(args[2]),
              width:canvas.width,height:canvas.height,at:Date.now()});
          }
        } catch { /* Observation must never affect rendering. */ }
        return result;
      };
    }
  }
})();
