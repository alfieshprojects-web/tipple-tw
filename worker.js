/**
 * TIPPLE Cloudflare Worker
 * - 靜態檔案（index.html, bars.json）由 Assets 提供
 * - GET /photo?ref=places/...&w=800 → 代理 Google Places 照片並快取 30 天
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === '/photo') {
      return handlePhoto(request, url, env);
    }

    return env.ASSETS.fetch(request);
  },
};

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
