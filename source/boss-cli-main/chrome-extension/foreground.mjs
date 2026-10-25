// BOSS dialog transitions and infinite scrolling require a rendered tab.
export async function foregroundTarget(chrome, tabId) {
  const tab=await chrome.tabs.get(tabId);
  let changed=false;
  if(tab.active===false) {
    await chrome.tabs.update(tabId,{active:true});
    changed=true;
  }
  if(chrome.windows?.get && Number.isInteger(tab.windowId)) {
    const window=await chrome.windows.get(tab.windowId);
    if(!window.focused || window.state==='minimized') {
      await chrome.windows.update(tab.windowId,{
        focused:true,...(window.state==='minimized'?{state:'normal'}:{})
      });
      changed=true;
    }
  }
  if(changed) await new Promise(resolve=>setTimeout(resolve,300));
}
