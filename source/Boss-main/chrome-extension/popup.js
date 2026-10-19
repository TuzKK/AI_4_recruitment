const status = document.querySelector('#status');
async function refresh() { const value=await chrome.storage.session.get('bridgeStatus'); status.textContent=value.bridgeStatus || '尚未连接'; }
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='session' && changes.bridgeStatus) refresh();});
document.querySelector('#connect').addEventListener('click',async()=>{
  const result=await chrome.runtime.sendMessage({type:'connect',token:document.querySelector('#token').value});
  if(result?.error) status.textContent=result.error;
  else {document.querySelector('#token').value=''; await refresh();}
});
document.querySelector('#disconnect').addEventListener('click',async()=>{
  await chrome.runtime.sendMessage({type:'disconnect'}); status.textContent='已断开，原浏览器保持打开';
});
refresh();
