/**
 * TIPPLE Cloudflare Worker
 * - 靜態檔案（index.html, bars.json）由 Assets 提供
 * - GET /photo?ref=places/...&w=800 → 代理 Google Places 照片並快取 30 天
 * - GET /translate?q=TEXT&tl=zh-TW → 翻譯代理，快取 30 天
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === '/photo') {
      return handlePhoto(request, url, env);
    }

    if (url.pathname === '/translate') {
      return handleTranslate(request, url);
    }

    return env.ASSETS.fetch(request);
  },
};

async function handleTranslate(request, url) {
  const q  = url.searchParams.get('q');
  const tl = url.searchParams.get('tl') || 'zh-TW';

  if (!q) return new Response('Missing q', { status: 400 });

  // 用翻譯內容當 cache key（前 120 字）
  const cacheKey = new Request(
    `https://tipple-translate/${tl}/${encodeURIComponent(q.slice(0, 120))}`,
    { method: 'GET' }
  );
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  // Google Translate 非官方免費端點（不需 API key）
  const gtUrl =
    `https://translate.googleapis.com/translate_a/single` +
    `?client=gtx&sl=auto&tl=${tl}&dt=t&q=${encodeURIComponent(q)}`;

  let gtResp;
  try {
    gtResp = await fetch(gtUrl);
  } catch (e) {
    return json({ error: e.message }, 502);
  }

  if (!gtResp.ok) {
    return json({ error: `translate failed: ${gtResp.status}` }, gtResp.status);
  }

  const data = await gtResp.json();
  // data[0] = [[translated_chunk, original_chunk], ...]
  const translated = (data[0] || []).map(c => c[0] || '').join('');

  const response = json({ text: translated }, 200, {
    'Cache-Control': 'public, max-age=2592000',
  });

  await cache.put(cacheKey, response.clone());
  return response;
}

function json(obj, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      ...extraHeaders,
    },
  });
}

async function handlePhoto(request, url, env) {
  const ref = url.searchParams.get('ref');
  const maxw = Math.min(parseInt(url.searchParams.get('w') || '800', 10), 1600);

  if (!ref) {
    return new Response('Missing ref', { status: 400 });
  }
  if (!env.GPHOTO_KEY) {
    return new Response('GPHOTO_KEY secret not set', { status: 500 });
  }

  // 用 request URL 當 cache key（正規化排序）
  const cacheUrl = new URL(request.url);
  cacheUrl.searchParams.sort();
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cache = caches.default;

  // 先查 Cloudflare 快取
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  // 從 Google Places API 取得照片（自動跟隨 redirect 拿到真實圖片）
  const googleUrl =
    `https://places.googleapis.com/v1/${ref}/media` +
    `?maxWidthPx=${maxw}&key=${env.GPHOTO_KEY}`;

  let imgResp;
  try {
    imgResp = await fetch(googleUrl, { redirect: 'follow' });
  } catch (e) {
    return new Response(`Fetch error: ${e.message}`, { status: 502 });
  }

  if (!imgResp.ok) {
    const body = await imgResp.text();
    return new Response(`Google error ${imgResp.status}: ${body}`, {
      status: imgResp.status,
    });
  }

  const contentType = imgResp.headers.get('content-type') || 'image/jpeg';
  const imgBytes = await imgResp.arrayBuffer();

  const response = new Response(imgBytes, {
    status: 200,
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'public, max-age=2592000, immutable',
      'Access-Control-Allow-Origin': '*',
    },
  });

  // 存入快取（await 確保完成）
  await cache.put(cacheKey, response.clone());

  return response;
}
