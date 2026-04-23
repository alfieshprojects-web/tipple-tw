/**
 * TIPPLE Cloudflare Worker
 * - 靜態檔案（index.html, bars.json）由 Assets 提供
 * - /photo?ref=...  → 代理 Google Places API 照片，並在 Cloudflare 快取 30 天
 *   如此每張照片 Google API 只被呼叫一次，之後永遠從 CDN 快取服務
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ── 照片代理路由 ──────────────────────────────────────────────────
    if (url.pathname === '/photo') {
      return handlePhoto(request, url, env);
    }

    // ── 其餘全部由靜態 Assets 提供（index.html, bars.json 等）────────
    return env.ASSETS.fetch(request);
  },
};

async function handlePhoto(request, url, env) {
  const ref = url.searchParams.get('ref');
  const maxw = parseInt(url.searchParams.get('w') || '800', 10);

  if (!ref || !ref.startsWith('places/')) {
    return new Response('Bad ref', { status: 400 });
  }

  // 用穩定的 cache key（不含 session 等雜訊）
  const cacheKey = new Request(
    `https://tipple-photo-cache/${encodeURIComponent(ref)}?w=${maxw}`,
    { method: 'GET' }
  );
  const cache = caches.default;

  // 1. 先查 Cloudflare 快取
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  // 2. 從 Google Places API 抓照片
  const apiKey = env.GPHOTO_KEY;
  if (!apiKey) return new Response('No API key configured', { status: 500 });

  const googleUrl =
    `https://places.googleapis.com/v1/${ref}/media` +
    `?maxWidthPx=${maxw}&skipHttpRedirect=true&key=${apiKey}`;

  let googleResp;
  try {
    googleResp = await fetch(googleUrl);
  } catch (e) {
    return new Response('Upstream fetch failed', { status: 502 });
  }

  if (!googleResp.ok) {
    return new Response(googleResp.statusText, { status: googleResp.status });
  }

  // Google 回傳 JSON（因為 skipHttpRedirect=true），裡面有 photoUri
  const json = await googleResp.json();
  const photoUri = json.photoUri;
  if (!photoUri) {
    return new Response('No photoUri in response', { status: 502 });
  }

  // 3. 實際抓圖片
  const imgResp = await fetch(photoUri);
  if (!imgResp.ok) {
    return new Response('Image fetch failed', { status: 502 });
  }

  const imgBytes = await imgResp.arrayBuffer();
  const contentType = imgResp.headers.get('content-type') || 'image/jpeg';

  // 4. 組合回應，快取 30 天
  const headers = new Headers({
    'Content-Type': contentType,
    'Cache-Control': 'public, max-age=2592000, immutable',
    'Access-Control-Allow-Origin': '*',
  });

  const response = new Response(imgBytes, { status: 200, headers });

  // 存入 Cloudflare 快取（非同步，不等待）
  event?.waitUntil?.(cache.put(cacheKey, response.clone()));
  // Workers 模組語法沒有 event，改用這種方式：
  cache.put(cacheKey, response.clone()); // fire and forget

  return response;
}
