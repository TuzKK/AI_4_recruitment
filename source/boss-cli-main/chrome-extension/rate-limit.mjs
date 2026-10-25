export const DEFAULT_RATE_LIMITS={request_seconds:5,greet_seconds:20};

export class BossRateLimiter {
  constructor({storage,now=Date.now,sleep=ms=>new Promise(r=>setTimeout(r,ms)),notify=async()=>{}}) {
    Object.assign(this,{storage,now,sleep,notify});
    this.tail=Promise.resolve();
    this.current={state:'idle',...DEFAULT_RATE_LIMITS};
  }
  serialize(fn) {
    const task=this.tail.then(fn);
    this.tail=task.catch(()=>{});
    return task;
  }
  async state() {
    return {last_request_at:0,last_greet_at:0,cooldown_until:0,...DEFAULT_RATE_LIMITS,
      ...(await this.storage.get('bossRateState')).bossRateState};
  }
  async configure(settings) {
    if(!settings) return;
    const {request_seconds:r,greet_seconds:g}=settings;
    if(!Number.isFinite(r)||r<5||r>30||!Number.isFinite(g)||g<20||g>60) throw Error('请求间隔须为5至30秒，打招呼间隔须为20至60秒');
    return this.serialize(async()=>{
      const state=await this.state();
      await this.storage.set({bossRateState:{...state,request_seconds:r,greet_seconds:g}});
    });
  }
  async publish(state) {this.current=state;await this.notify(state);}
  run(kind,deadline,fn,readSignals=async()=>[]) {
    return this.serialize(async()=>{
      const state=await this.state();
      const limits={request_seconds:state.request_seconds,greet_seconds:state.greet_seconds};
      const observe=async()=>{
        const previous=state.last_signal_at||0;
        let changed=false;
        for(const signal of await readSignals()) {
          if(!signal || !Number.isFinite(signal.at) || signal.at<=previous || (signal.status!==429&&signal.code!==9))continue;
          const raw=signal.retry_after;
          const seconds=typeof raw==='string'&&/^\d+(\.\d+)?$/.test(raw.trim())?Number(raw):0;
          const date=typeof raw==='string'?Date.parse(raw):NaN;
          state.cooldown_until=Math.max(state.cooldown_until,this.now()+120000,this.now()+seconds*1000,Number.isFinite(date)?date:0,
            Number.isFinite(signal.cooldown_until)?signal.cooldown_until:0);
          state.last_signal_at=Math.max(state.last_signal_at||0,signal.at);changed=true;
        }
        if(changed)await this.storage.set({bossRateState:state});
        if(state.cooldown_until>this.now()) {
          await this.publish({...limits,state:'cooldown',until:state.cooldown_until});
          throw Object.assign(Error('BOSS限流冷却中，请等待后恢复任务'),{rate_limited:true});
        }
      };
      await observe();
      if(state.cooldown_until>this.now()) {
        await this.publish({...limits,state:'cooldown',until:state.cooldown_until});
        throw Object.assign(Error('BOSS限流冷却中，请等待后恢复任务'),{rate_limited:true});
      }
      const due=Math.max(state.last_request_at+state.request_seconds*1000,
        kind==='greet'?state.last_greet_at+state.greet_seconds*1000:0);
      if(Math.max(due,this.now())>=deadline-1500) {
        await this.publish({...limits,state:'waiting',until:due});
        throw Object.assign(Error('限速等待超过本次执行期限，尚未执行，请稍后恢复'),{rate_limited:true});
      }
      while(this.now()<due) {
        await this.publish({...limits,state:'waiting',until:due});
        await this.sleep(Math.min(1000,due-this.now()));
      }
      if(this.now()>=deadline-1500) throw Object.assign(Error('限速等待已超时，尚未执行'),{rate_limited:true});
      await observe();
      const started=this.now();
      state.last_request_at=started;
      if(kind==='greet') state.last_greet_at=started;
      await this.storage.set({bossRateState:state});
      await this.publish({...limits,state:'executing',last_request_at:started,until:0});
      try {
        const response=await fn();
        await observe();
        if(response?.status===429 || response?.body?.code===9) {
          const raw=response.retry_after;
          const seconds=typeof raw==='string' && /^\d+(\.\d+)?$/.test(raw.trim())?Number(raw):0;
          const date=typeof raw==='string'?Date.parse(raw):NaN;
          state.cooldown_until=Math.max(this.now()+120000,this.now()+seconds*1000,Number.isFinite(date)?date:0);
          await this.storage.set({bossRateState:state});
          await this.publish({...limits,state:'cooldown',until:state.cooldown_until});
          throw Object.assign(Error('BOSS返回限流，任务已暂停，至少冷却120秒后恢复'),{rate_limited:true});
        }
        return response;
      } finally {
        // Conservative spacing from completion also covers storage/heartbeat
        // latency before the network dispatch, rather than shortening the gap.
        state.last_request_at=this.now();
        if(kind==='greet') state.last_greet_at=this.now();
        await this.storage.set({bossRateState:state});
        if(this.current.state==='executing') await this.publish({...limits,state:'idle',last_request_at:started,until:0});
      }
    });
  }
}
