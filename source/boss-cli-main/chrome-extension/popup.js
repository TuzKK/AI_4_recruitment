const byId=id=>document.getElementById(id);
async function show() {byId('status').textContent=(await chrome.storage.session.get('status')).status || '尚未连接';}
chrome.storage.local.get(['port','token']).then(c=>{byId('port').value=c.port || 17891;byId('token').value=c.token || '';});
byId('connect').onclick=async()=>{
  const port=Number(byId('port').value),token=byId('token').value.trim();
  if (!Number.isInteger(port) || port<1024 || port>65535 || token.length<20) {byId('status').textContent='请检查端口与配对令牌';return;}
  await chrome.storage.local.set({port,token,enabled:true});
  await chrome.runtime.sendMessage({action:'connect'});
  byId('status').textContent='正在连接…';
};
byId('disconnect').onclick=async()=>{
  await chrome.storage.local.set({enabled:false});await chrome.runtime.sendMessage({action:'disconnect'});
  await chrome.storage.session.set({status:'已断开'});await show();
};
chrome.storage.onChanged.addListener(show);
void show();

async function showCapturePermission() {
 try {
  const granted=await chrome.permissions.contains({permissions:['debugger']});
  byId('capture-status').textContent=granted?'截图权限可用；可以返回终端采集':'截图权限缺失：请在 chrome://extensions 重新加载 0.2.2 版连接器并确认 Chrome 提示（若有）';
 } catch(error) {
  byId('capture-status').textContent='权限检查失败：'+error.message;
 }
}
byId('capture-permission').onclick=showCapturePermission;
void showCapturePermission();
