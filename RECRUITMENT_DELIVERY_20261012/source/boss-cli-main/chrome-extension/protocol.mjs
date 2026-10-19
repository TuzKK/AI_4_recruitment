export const READ_ROUTES = [
  ['GET','/wapi/zpjob/job/chatted/jobList'], ['POST','/wapi/zprelation/friend/filterByLabel'],
  ['POST','/wapi/zprelation/friend/getBossFriendListV2.json'], ['POST','/wapi/zpchat/boss/userLastMsg'],
  ['GET','/wapi/zpchat/boss/historyMsg'], ['GET','/wapi/zpjob/chat/geek/info'],
  ['GET','/wapi/zpjob/view/geek/info'], ['GET','/wapi/zprelation/friend/label/get'],
  ['GET','/wapi/zprelation/friend/getNoteAndLabels'], ['GET','/wapi/zprelation/friend/greetSort/getList'],
  ['GET','/wapi/zprelation/friend/greetRecSortList'], ['GET','/wapi/zpitem/web/boss/search/geek/info'],
  ['GET','/wapi/zpinterview/boss/interview/valid/list'], ['GET','/wapi/zpuser/wap/getUserInfo.json']
];
const WRITES = [['POST','/wapi/zpchat/fastReply/sendReplyMsg'], ['POST','/wapi/zpchat/session/bossEnter']];
export function validateApi(args) {
  if (![...READ_ROUTES,...WRITES].some(([method,path]) => args.method === method && args.path === path)) {
    throw new Error('不支持的 API 操作');
  }
}
export function isBossUrl(value) {
  try { const u=new URL(value); return u.protocol === 'https:' && ['www.zhipin.com','zhipin.com'].includes(u.hostname); }
  catch { return false; }
}
export function classify(url, frames) {
  const path=new URL(url).pathname;
  if (frames.some(x=>x.verify) || /\/verify|\/captcha|\/safe\//.test(path)) return 'verification_required';
  if (frames.some(x=>x.login) || /\/login|\/web\/user\//.test(path)) return 'not_logged_in';
  if (path.startsWith('/web/geek/')) return 'wrong_role';
  if ((path.startsWith('/web/chat') || path.startsWith('/web/boss')) && frames.some(x=>x.content || x.account)) return 'logged_in';
  return 'unknown';
}
export function parseTarget(target) {
  const m=/^(\d+):([A-Za-z0-9-]+)$/.exec(target);
  if (!m) throw new Error('无效页面标识');
  return {tabId:Number(m[1]),documentId:m[2]};
}
