// Passive metadata only: never retain candidate data or send network requests.
(()=>{
  if(globalThis.__bossRateObserverInstalled || location.protocol!=='https:' ||
      !['www.zhipin.com','zhipin.com','m.zhipin.com'].includes(location.hostname)) return;
  globalThis.__bossRateObserverInstalled=true;
  const eligible=value=>{try{const u=new URL(value,location.href);return u.protocol==='https:'&&
    ['www.zhipin.com','zhipin.com','m.zhipin.com'].includes(u.hostname)&&u.pathname.startsWith('/wapi/');}catch{return false;}};
  const record=(status,code,retry)=>{
    if(status!==429&&code!==9)return;
    const previous=globalThis.__bossRateLimitSignal;
    const now=Date.now();
    const seconds=typeof retry==='string'&&/^\d+(\.\d+)?$/.test(retry.trim())?Number(retry):0;
    const date=typeof retry==='string'?Date.parse(retry):NaN;
    const cooldown_until=Math.max(previous?.cooldown_until||0,now+120000,now+seconds*1000,Number.isFinite(date)?date:0);
    globalThis.__bossRateLimitSignal={at:Math.max(now,(previous?.at||0)+1),status,code,retry_after:retry||null,cooldown_until};
  };
  if(globalThis.XMLHttpRequest){
    const original=XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open=function(method,url,...rest){
      if(eligible(url))this.addEventListener('loadend',()=>{
        try{
          if(this.status===429)return record(429,null,this.getResponseHeader('Retry-After'));
          let data=this.responseType==='json'?this.response:null;
          if(!data&&(!this.responseType||this.responseType==='text')&&this.responseText?.length<2000000){
            data=JSON.parse(this.responseText);
          }
          record(this.status,data?.code,this.getResponseHeader('Retry-After'));
        }catch{ /* Observation never changes page behavior. */ }
      },{once:true});
      return Reflect.apply(original,this,[method,url,...rest]);
    };
  }
  if(typeof globalThis.fetch==='function'){
    const original=globalThis.fetch;
    globalThis.fetch=function(input,...rest){
      const result=Reflect.apply(original,this,[input,...rest]);
      if(!eligible(typeof input==='string'?input:input?.url||String(input)))return result;
      return result.then(response=>{
        if(response.status===429)record(429,null,response.headers.get('Retry-After'));
        else if(/json/i.test(response.headers.get('Content-Type')||'')&&Number(response.headers.get('Content-Length')||0)<2000000){
          void response.clone().text().then(text=>{
            if(text.length<2000000)record(response.status,JSON.parse(text)?.code,response.headers.get('Retry-After'));
          }).catch(()=>{});
        }
        return response;
      });
    };
  }
})();
