/**
 * TIPPLE Cloudflare Worker v2.0
 * - 靜態檔案（index.html, bars.json）由 Assets 提供
 * - GET  /photo?ref=...&w=800       → 代理 Google Places 照片（快取 30 天）
 * - GET  /translate?q=TEXT&tl=zh-TW → 翻譯代理（快取 30 天）
 * - POST /auth/google               → Google One Tap 登入，回傳 session token
 * - GET  /auth/me                   → 取得目前登入用戶
 * - POST /auth/logout               → 登出（刪除 session）
 * - GET  /api/reviews?bar_id=X      → 取得酒吧的社群評論
 * - POST /api/reviews               → 新增/更新評論（需登入）
 * - DELETE /api/reviews/:id         → 刪除自己的評論（需登入）
 * - POST /api/reviews/:id/helpful   → 標記有幫助（需登入）
 */

const SESSION_TTL = 30 * 24 * 60 * 60 * 1000; // 30天（毫秒）
const POINTS_NEW_REVIEW   = 10;
const POINTS_FIRST_REVIEW = 5;   // 第一則評論加碼

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    if (url.pathname === '/photo')    return handlePhoto(request, url, env);
    if (url.pathname === '/translate') return handleTranslate(request, url);
    if (url.pathname.startsWith('/auth/'))      return handleAuth(request, url, env);
    if (url.pathname.startsWith('/api/reviews')) return handleReviews(request, url, env);

    return env.ASSETS.fetch(request);
  },
};

/* ============================================================
   AUTH
   ============================================================ */
async function handleAuth(request, url, env) {
  const path = url.pathname;

  // POST /auth/google
  if (path === '/auth/google' && request.method === 'POST') {
    try {
      const { credential } = await request.json();
      if (!credential) return json({ error: 'Missing credential' }, 400);

      // 用 Google tokeninfo 端點驗證（無需管理公鑰）
      const tResp = await fetch(
        `https://oauth2.googleapis.com/tokeninfo?id_token=${credential}`
      );
      if (!tResp.ok) return json({ error: 'Invalid Google token' }, 401);
      const payload = await tResp.json();

      // 驗證 audience
      if (env.GOOGLE_CLIENT_ID && payload.aud !== env.GOOGLE_CLIENT_ID) {
        return json({ error: 'Token audience mismatch' }, 401);
      }

      const userId = payload.sub;
      const now = Date.now();

      // Upsert user
      await env.DB.prepare(`
        INSERT INTO users(id, name, email, avatar, created_at)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET name=excluded.name, email=excluded.email, avatar=excluded.avatar
      `).bind(userId, payload.name, payload.email, payload.picture, now).run();

      // 建立 session
      const token = generateToken();
      await env.DB.prepare(`
        INSERT INTO sessions(token, user_id, expires_at) VALUES(?, ?, ?)
      `).bind(token, userId, now + SESSION_TTL).run();

      const user = await env.DB.prepare('SELECT * FROM users WHERE id=?').bind(userId).first();
      return json({ token, user });

    } catch (e) {
      return json({ error: e.message }, 500);
    }
  }

  // GET /auth/me
  if (path === '/auth/me' && request.method === 'GET') {
    const user = await requireAuth(request, env);
    if (!user) return json({ error: 'Unauthorized' }, 401);
    return json({ user });
  }

  // POST /auth/logout
  if (path === '/auth/logout' && request.method === 'POST') {
    const token = getBearerToken(request);
    if (token) await env.DB.prepare('DELETE FROM sessions WHERE token=?').bind(token).run();
    return json({ ok: true });
  }

  return json({ error: 'Not found' }, 404);
}

/* ============================================================
   REVIEWS
   ============================================================ */
async function handleReviews(request, url, env) {
  const path = url.pathname;

  // GET /api/reviews?bar_id=X
  if (path === '/api/reviews' && request.method === 'GET') {
    const barId = parseInt(url.searchParams.get('bar_id'));
    if (!barId) return json({ error: 'Missing bar_id' }, 400);

    const rows = await env.DB.prepare(`
      SELECT r.id, r.user_id, r.bar_id, r.rating, r.text, r.created_at, r.updated_at,
             u.name as user_name, u.avatar as user_avatar, u.points as user_points,
             (SELECT COUNT(*) FROM helpful_votes WHERE review_id=r.id) as helpful_count
      FROM reviews r
      JOIN users u ON r.user_id = u.id
      WHERE r.bar_id = ?
      ORDER BY r.created_at DESC
    `).bind(barId).all();

    const reviews = rows.results || [];
    const avgRating = reviews.length
      ? reviews.reduce((s, r) => s + r.rating, 0) / reviews.length
      : null;

    return json({ reviews, avg_rating: avgRating, count: reviews.length });
  }

  // POST /api/reviews  (新增或更新)
  if (path === '/api/reviews' && request.method === 'POST') {
    const user = await requireAuth(request, env);
    if (!user) return json({ error: 'Unauthorized' }, 401);

    const { bar_id, rating, text } = await request.json();
    if (!bar_id || !rating || !text) return json({ error: 'Missing fields' }, 400);
    if (rating < 1 || rating > 5)    return json({ error: 'Rating must be 1–5' }, 400);
    if (text.trim().length < 10)     return json({ error: 'Review too short' }, 400);

    const now = Date.now();

    // 是否已有評論
    const existing = await env.DB.prepare(
      'SELECT id FROM reviews WHERE user_id=? AND bar_id=?'
    ).bind(user.id, bar_id).first();

    if (existing) {
      // 更新
      await env.DB.prepare(`
        UPDATE reviews SET rating=?, text=?, updated_at=? WHERE id=?
      `).bind(rating, text.trim(), now, existing.id).run();
    } else {
      // 新增
      await env.DB.prepare(`
        INSERT INTO reviews(user_id, bar_id, rating, text, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?)
      `).bind(user.id, bar_id, rating, text.trim(), now, now).run();

      // 積分：是否第一則評論
      const barCount = await env.DB.prepare(
        'SELECT COUNT(*) as cnt FROM reviews WHERE bar_id=?'
      ).bind(bar_id).first();
      const bonus = (barCount?.cnt === 1) ? POINTS_FIRST_REVIEW : 0;
      await env.DB.prepare(
        'UPDATE users SET points = points + ? WHERE id=?'
      ).bind(POINTS_NEW_REVIEW + bonus, user.id).run();
    }

    const review = await env.DB.prepare(`
      SELECT r.*, u.name as user_name, u.avatar as user_avatar, u.points as user_points,
             0 as helpful_count
      FROM reviews r JOIN users u ON r.user_id=u.id
      WHERE r.user_id=? AND r.bar_id=?
    `).bind(user.id, bar_id).first();

    return json({ review, points: (await env.DB.prepare('SELECT points FROM users WHERE id=?').bind(user.id).first())?.points });
  }

  // DELETE /api/reviews/:id
  const delMatch = path.match(/^\/api\/reviews\/(\d+)$/);
  if (delMatch && request.method === 'DELETE') {
    const user = await requireAuth(request, env);
    if (!user) return json({ error: 'Unauthorized' }, 401);
    const reviewId = parseInt(delMatch[1]);
    const row = await env.DB.prepare('SELECT user_id FROM reviews WHERE id=?').bind(reviewId).first();
    if (!row) return json({ error: 'Not found' }, 404);
    if (row.user_id !== user.id) return json({ error: 'Forbidden' }, 403);
    await env.DB.prepare('DELETE FROM reviews WHERE id=?').bind(reviewId).run();
    // 扣回積分
    await env.DB.prepare('UPDATE users SET points = MAX(0, points - ?) WHERE id=?')
      .bind(POINTS_NEW_REVIEW, user.id).run();
    return json({ ok: true });
  }

  // POST /api/reviews/:id/helpful
  const helpMatch = path.match(/^\/api\/reviews\/(\d+)\/helpful$/);
  if (helpMatch && request.method === 'POST') {
    const user = await requireAuth(request, env);
    if (!user) return json({ error: 'Unauthorized' }, 401);
    const reviewId = parseInt(helpMatch[1]);

    const review = await env.DB.prepare('SELECT user_id FROM reviews WHERE id=?').bind(reviewId).first();
    if (!review) return json({ error: 'Not found' }, 404);
    if (review.user_id === user.id) return json({ error: 'Cannot vote own review' }, 400);

    const existing = await env.DB.prepare(
      'SELECT 1 FROM helpful_votes WHERE user_id=? AND review_id=?'
    ).bind(user.id, reviewId).first();

    if (existing) {
      await env.DB.prepare('DELETE FROM helpful_votes WHERE user_id=? AND review_id=?')
        .bind(user.id, reviewId).run();
      await env.DB.prepare('UPDATE users SET points = MAX(0, points - 2) WHERE id=?')
        .bind(review.user_id).run();
      return json({ helpful: false });
    } else {
      await env.DB.prepare('INSERT INTO helpful_votes(user_id, review_id) VALUES(?, ?)')
        .bind(user.id, reviewId).run();
      await env.DB.prepare('UPDATE users SET points = points + 2 WHERE id=?')
        .bind(review.user_id).run();
      return json({ helpful: true });
    }
  }

  return json({ error: 'Not found' }, 404);
}

/* ============================================================
   HELPERS
   ============================================================ */
function generateToken() {
  const arr = new Uint8Array(32);
  crypto.getRandomValues(arr);
  return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
}

function getBearerToken(request) {
  const auth = request.headers.get('Authorization') || '';
  return auth.startsWith('Bearer ') ? auth.slice(7) : null;
}

async function requireAuth(request, env) {
  const token = getBearerToken(request);
  if (!token) return null;
  const session = await env.DB.prepare(
    'SELECT user_id, expires_at FROM sessions WHERE token=?'
  ).bind(token).first();
  if (!session || session.expires_at < Date.now()) return null;
  return env.DB.prepare('SELECT * FROM users WHERE id=?').bind(session.user_id).first();
}

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
  };
}

function json(obj, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(), ...extraHeaders },
  });
}

/* ============================================================
   PHOTO PROXY
   ============================================================ */
async function handlePhoto(request, url, env) {
  const ref  = url.searchParams.get('ref');
  const maxw = Math.min(parseInt(url.searchParams.get('w') || '800', 10), 1600);
  if (!ref) return new Response('Missing ref', { status: 400 });
  if (!env.GPHOTO_KEY) return new Response('GPHOTO_KEY not set', { status: 500 });

  const cacheUrl = new URL(request.url);
  cacheUrl.searchParams.sort();
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const googleUrl = `https://places.googleapis.com/v1/${ref}/media?maxWidthPx=${maxw}&key=${env.GPHOTO_KEY}`;
  let imgResp;
  try { imgResp = await fetch(googleUrl, { redirect: 'follow' }); }
  catch (e) { return new Response(`Fetch error: ${e.message}`, { status: 502 }); }

  if (!imgResp.ok) {
    const body = await imgResp.text();
    return new Response(`Google error ${imgResp.status}: ${body}`, { status: imgResp.status });
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
  await cache.put(cacheKey, response.clone());
  return response;
}

/* ============================================================
   TRANSLATE PROXY
   ============================================================ */
async function handleTranslate(request, url) {
  const q  = url.searchParams.get('q');
  const tl = url.searchParams.get('tl') || 'zh-TW';
  if (!q) return new Response('Missing q', { status: 400 });

  const cacheKey = new Request(
    `https://tipple-translate/${tl}/${encodeURIComponent(q.slice(0, 120))}`,
    { method: 'GET' }
  );
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const gtUrl = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${tl}&dt=t&q=${encodeURIComponent(q)}`;
  let gtResp;
  try { gtResp = await fetch(gtUrl); }
  catch (e) { return json({ error: e.message }, 502); }

  if (!gtResp.ok) return json({ error: `translate failed: ${gtResp.status}` }, gtResp.status);

  const data = await gtResp.json();
  const translated = (data[0] || []).map(c => c[0] || '').join('');
  const response = json({ text: translated }, 200, { 'Cache-Control': 'public, max-age=2592000' });
  await cache.put(cacheKey, response.clone());
  return response;
}
