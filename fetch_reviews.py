"""
TIPPLE — 評論抓取腳本 v5.0
==============================
策略：
  - 目標城市：台北 / 新北
  - 每間酒吧最多 13 則：
      中文（zh-TW + zh）正評 ≤ 8 則
      負評（1–2★，任意語言）≤ 5 則
      英文正評 ≤ 2 則
  - 多語系抓取：zh-TW / zh / en / ja / ko
    → 不同語系回傳不同評論池，大幅提高負評撈取率
  - 負評定義：rating ≤ 2（含 2★，不再只抓 1★）
  - 同時抓取 generativeSummary
  - 排序：文字長度 × 0.6 + 新舊程度 × 0.4

執行方式：
  python3 fetch_reviews.py              # 全部重抓
  python3 fetch_reviews.py --skip-existing  # 跳過已有評論的酒吧
  python3 fetch_reviews.py --min 4.2    # 只抓 4.2 分以上

費用估算：
  每間酒吧 5 次 Details call × $0.003 = $0.015
  2137 間 ≈ $32
"""

import requests
import json
import time
import argparse
from datetime import datetime, timezone

GOOGLE_API_KEY = "AIzaSyCpm-WmlRkoytWw7NLanyjWBZ82U-aUqqI"
INPUT_FILE     = "bars.json"
OUTPUT_FILE    = "bars.json"
DELAY          = 0.15

# 目標城市
TARGET_AREAS = {'taipei', 'newtaipei'}

# 每間酒吧的評論組成
MAX_ZH  = 8   # 中文正評上限
MAX_EN  = 2   # 英文正評上限
MAX_NEG = 5   # 負評（1–2★）上限（任意語言）

# 多語系抓取順序（不同語系回傳不同評論池，增加負評撈取率）
LANG_CODES = ["zh-TW", "zh", "en", "ja", "ko"]

def fetch_place_data(place_id: str, lang: str) -> dict:
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "reviews,generativeSummary",
        "Accept-Language": lang,
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"   ⚠ [{lang}] {e}")
        return {}

def parse_publish_time(t: str) -> float:
    if not t:
        return 0.0
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0

def score_review(r: dict, now_ts: float) -> float:
    text_len = len(r.get("text", ""))
    days_old = max(0, (now_ts - r.get("_pub_ts", 0.0)) / 86400)
    recency  = max(0.0, 1.0 - days_old / 365)
    return text_len * 0.6 + recency * 400

def process_raw_reviews(raw_list: list) -> list:
    result = []
    for r in raw_list:
        text = (r.get("text") or {}).get("text", "").strip()
        if not text:
            continue
        result.append({
            "author":  r.get("authorAttribution", {}).get("displayName", "匿名"),
            "rating":  r.get("rating", 0),
            "text":    text[:600],
            "time":    r.get("relativePublishTimeDescription", ""),
            "lang":    (r.get("text") or {}).get("languageCode", ""),
            "_pub_ts": parse_publish_time(r.get("publishTime", "")),
        })
    return result

def dedup_and_sort(reviews: list, now_ts: float) -> list:
    seen, out = set(), []
    for r in reviews:
        key = r["text"][:60]
        if key not in seen:
            seen.add(key)
            out.append(r)
    out.sort(key=lambda r: score_review(r, now_ts), reverse=True)
    for r in out:
        r.pop("_pub_ts", None)
    return out

def extract_summary(data_list: list) -> str:
    for d in data_list:
        gs = d.get("generativeSummary", {})
        for field in ["overview", "description"]:
            text = (gs.get(field) or {}).get("text", "").strip()
            if text:
                return text
    return ""

def main():
    parser = argparse.ArgumentParser(description="TIPPLE 評論抓取腳本 v4.0")
    parser.add_argument("--min",           type=float, default=0.0,  help="最低 Google 評分門檻（預設 0=全部）")
    parser.add_argument("--skip-existing", action="store_true",      help="跳過已有評論的酒吧")
    args = parser.parse_args()

    print("🍸 TIPPLE 評論抓取腳本 v5.0")
    print(f"   目標城市：台北 / 新北")
    print(f"   評論組成：中文正評 ≤{MAX_ZH} + 英文正評 ≤{MAX_EN} + 負評(1-2★) ≤{MAX_NEG}")
    print(f"   語系抓取：{' / '.join(LANG_CODES)}")
    print(f"   開始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw = f.read()
    data = json.loads(raw)
    bars = data.get("bars", [])

    # 篩選目標
    targets = [b for b in bars
               if b.get("google_place_id")
               and b.get("area") in TARGET_AREAS
               and b.get("google_rating", 0) >= args.min]
    targets.sort(key=lambda b: b.get("google_rating", 0), reverse=True)
    if args.skip_existing:
        targets = [b for b in targets if not b.get("review_list")]

    print(f"📋 目標：{len(targets)} 間酒吧")
    print(f"   預計費用：約 ${len(targets) * 0.015:.1f} USD（5 calls / 間）\n")

    ok = fail = summary_count = 0
    now_ts = datetime.now(timezone.utc).timestamp()

    for i, bar in enumerate(targets, 1):
        pid  = bar["google_place_id"]
        name = bar.get("name", pid)
        print(f"[{i:4d}/{len(targets)}] {name[:32]:<32}", end=" ", flush=True)

        # ── 多語系抓取，彙整所有評論 ────────────────────────────────
        all_raw = []
        lang_data = {}
        for lc in LANG_CODES:
            d = fetch_place_data(pid, lc)
            lang_data[lc] = d
            all_raw += process_raw_reviews(d.get("reviews", []))
            time.sleep(DELAY)

        # 全語系去重（以評論前 60 字為 key）
        seen, all_uniq = set(), []
        for r in all_raw:
            key = r["text"][:60]
            if key not in seen:
                seen.add(key); all_uniq.append(r)

        # ── 分類 ──────────────────────────────────────────────────
        is_neg = lambda r: r.get("rating", 5) <= 2

        # 負評池：1–2★，任意語言，依文字長度排序（越詳細越優先）
        neg_pool = sorted(
            [r for r in all_uniq if is_neg(r) and r.get("text","")],
            key=lambda r: len(r.get("text","")), reverse=True
        )[:MAX_NEG]
        neg_ids = set(id(r) for r in neg_pool)

        # 中文正評池
        zh_pos = [r for r in all_uniq
                  if not is_neg(r) and id(r) not in neg_ids
                  and (not r.get("lang") or r["lang"].startswith("zh"))]
        zh_pos = dedup_and_sort(zh_pos, now_ts)[:MAX_ZH]
        zh_ids = set(id(r) for r in zh_pos)

        # 英文正評池
        en_pos = [r for r in all_uniq
                  if not is_neg(r) and id(r) not in neg_ids and id(r) not in zh_ids
                  and r.get("lang","").startswith("en")]
        en_pos = dedup_and_sort(en_pos, now_ts)[:MAX_EN]

        merged = zh_pos + en_pos + neg_pool
        summary = extract_summary([lang_data.get("zh-TW",{}), lang_data.get("en",{})])

        if merged:
            bar["review_list"]    = merged
            bar["review_summary"] = summary
            ok += 1
            summary_count += (1 if summary else 0)
            neg_str = f" 👎{len(neg_pool)}" if neg_pool else ""
            print(f"✓ zh:{len(zh_pos)} en:{len(en_pos)}{neg_str}  {'📝' if summary else '  '}")
        else:
            bar["review_list"]    = []
            bar["review_summary"] = ""
            fail += 1
            print("— 無評論")

        # 每 100 筆存一次
        if i % 100 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n   💾 已儲存進度（{i}/{len(targets)}）\n")

    # 最終儲存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_rev = sum(len(b.get("review_list", [])) for b in bars)
    print(f"\n✅ 完成！成功 {ok} 間，無評論 {fail} 間")
    print(f"   評論總則數：{total_rev}")
    print(f"   有 AI 摘要：{summary_count} 間")
    print(f"   輸出：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()
