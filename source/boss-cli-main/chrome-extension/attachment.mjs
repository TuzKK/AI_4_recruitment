const PREVIEW_ORIGIN = 'https://m.zhipin.com';
const PREVIEW_PATH = '/wflow/zpgeek/download/preview4boss';
const MAX_BYTES = 5_000_000;

export function selectAttachmentUrl(messages, gid, mid) {
  if (!Number.isSafeInteger(gid) || gid <= 0 || !/^[0-9]{1,30}$/.test(String(mid))) {
    throw new Error('Invalid attachment identity');
  }
  const matches = (Array.isArray(messages) ? messages : []).filter(message =>
    String(message?.mid) === String(mid) && message?.from?.uid === gid &&
    message?.bizType === 13 && message?.body?.type === 12 &&
    message?.body?.hyperLink?.hyperLinkType === 1);
  if (matches.length !== 1) throw new Error('Attachment message missing or ambiguous');
  const wrapper = new URL(matches[0].body.hyperLink.url);
  if (wrapper.protocol !== 'bosszp:' || wrapper.hostname !== 'bosszhipin.app' ||
      wrapper.pathname !== '/openwith') {
    throw new Error('Unexpected attachment wrapper');
  }
  const values = wrapper.searchParams.getAll('url');
  if (values.length !== 1) throw new Error('Attachment URL missing or ambiguous');
  const preview = new URL(values[0]);
  if (preview.origin !== PREVIEW_ORIGIN || preview.pathname !== PREVIEW_PATH ||
      preview.username || preview.password) throw new Error('Unexpected attachment endpoint');
  return preview.href;
}

// Serialized into a temporary same-origin m.zhipin.com tab. Cookies stay in Chrome.
export async function fetchAttachmentPage(url, deadline) {
  const previewOrigin = 'https://m.zhipin.com';
  const previewPath = '/wflow/zpgeek/download/preview4boss';
  const maxBytes = 5_000_000;
  const parsed = new URL(url);
  if (location.origin !== previewOrigin || parsed.origin !== previewOrigin ||
      parsed.pathname !== previewPath || Date.now() >= deadline) {
    throw new Error('Invalid attachment page or expired command');
  }
  const response = await fetch(parsed.href, {credentials:'include',cache:'no-store',
    signal:AbortSignal.timeout(Math.max(1, Math.min(18000, deadline-Date.now()-1000)))});
  const contentType = response.headers.get('Content-Type') || '';
  const expectedSize = Number(response.headers.get('Content-Length') || 0);
  if (!response.ok || !/application\/pdf|application\/octet-stream/i.test(contentType) ||
      expectedSize > maxBytes) throw new Error(`Attachment did not return a bounded PDF (HTTP ${response.status})`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.length < 8 || bytes.length > maxBytes ||
      String.fromCharCode(...bytes.slice(0,5)) !== '%PDF-') {
    throw new Error('Attachment response is not a PDF');
  }
  let binary = '';
  for (let i=0;i<bytes.length;i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
  return {bytes:bytes.length,content_type:contentType,base64:btoa(binary)};
}
