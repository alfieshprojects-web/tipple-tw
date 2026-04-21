"""
TIPPLE — 評論抓取腳本 v2.0
==============================
策略：每間酒吧打兩次 API（中文 + 英文），最多取 10 則不重複評論。
排序：文字長度（越長越有幫助）× 0.6 + 新舊程度 × 0.4

執行方式：
  python3 fetch_reviews.py              # 全部重抓
  python3 fetch_reviews.py --top 500    # 只抓前 500 間高分酒吧
  python3 fetch_reviews.py --skip-existing  # 跳過已有評論

費用估算：
  每間酒吧 2 次 Details call × $0.003 差額 = $0.006
  500 間 ≈ $3，全部 3928 間 ≈ $24
"""

import requests
import json
import time
import argparse
from datetime import datetime, timezone

GOOGLE_API_KEY = "AIzaSyCpm-WmlRkoytWw7NLanyjWBZ82U-aUqqI"
INPUT_FILE     = "bars.json"
OUTPUT_FILE    = "bars.json"
DELAY          = 0.15   # 每次請求間隔（秒）
MAX_REVIEWS    = 10     # 最多保留幾則

def fetch_reviews_lang(place_id: str, lang: str) -> list:
    """呼叫 Places API (New) 抓取指定語言評論（最多 5 則）"""
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "reviews",
        "Accept-Language": lang,
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("reviews", [])
    except Exception as e:
        print(f"   ⚠ [{lang}] {e}")
        return []

def parse_publish_time(t: str) -> float:
    """把 ISO 8601 時間字串轉成 Unix timestamp（秒）"""
    if not t:
        return 0.0
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0

def score_review(r: dict, now_ts: float) -> float:
    """
    評論排序分數（越高越前面）：
      60% 文字長度（有幫助度）
      40% 新舊程度（最近一年最高分）
    """
    text_len  = len(r.get("text", ""))
    pub_ts    = r.get("_pub_ts", 0.0)
    days_old  = max(0, (now_ts - pub_ts) / 86400)
    recency   = max(0.0, 1.0 - days_old / 365)   # 1 年內線性衰減
    return text_len * 0.6 + recency * 400          # 乘以 400 讓量級相近

def process_raw_reviews(raw_list: list) -> list:
    """把 API 原始資料轉成乾淨格式"""
    result = []
    for r in raw_list:
        text = (r.get("text") or {}).get("text", "").strip()
        if not text:
            continue
        pub_str = r.get("publishTime", "")
        result.append({
            "author":  r.get("authorAttribution", {}).get("displayName", "匿名"),
            "rating":  r.get("rating", 0),
            "text":    text[:500],
            "time":    r.get("relativePublishTimeDescription", ""),
            "lang":    (r.get("text") or {}).get("languageCode", ""),
            "_pub_ts": parse_publish_time(pub_str),
        })
    return result

def merge_and_sort(zh_reviews: list, en_reviews: list) -> list:
    """合併中英評論，去重，依分數排序，取前 MAX_REVIEWS 則"""
    seen  = set()
    merged = []
    for r in zh_reviews + en_reviews:
        key = r["text"][:60]   # 用前 60 字去重
        if key not in seen:
            seen.add(key)
            merged.append(r)

    now_ts = datetime.now(timezone.utc).timestamp()
    merged.sort(key=lambda r: score_review(r, now_ts), reverse=True)

    # 移除內部用的暫存欄位
    for r in merged:
        r.pop("_pub_ts", None)

    return merged[:MAX_REVIEWS]

def main():
    parser = argparse.ArgumentParser(description="TIPPLE 評論抓取腳本 v2.0")
    parser.add_argument("--top",           type=int,   default=0,   help="只抓評分最高的前 N 間（0=全部）")
    parser.add_argument("--min",           type=float, default=4.0, help="最低 Google 評分門檻（預設 4.0）")
    parser.add_argument("--skip-existing", action="store_true",     help="跳過已有評論的酒吧")
    args = parser.parse_args()

    print("🍸 TIPPLE 評論抓取腳本 v2.0")
    print(f"   策略：zh-TW + en 各 5 則 → 去重排序 → 最多 {MAX_REVIEWS} 則")
    print(f"   開始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    bars = data.get("bars", [])

    # 篩選目標
    targets = [b for b in bars if b.get("google_place_id") and
               b.get("google_rating", 0) >= args.min]
    targets.sort(key=lambda b: b.get("google_rating", 0), reverse=True)
    if args.top > 0:
        targets = targets[:args.top]
    if args.skip_existing:
        targets = [b for b in targets if not b.get("review_list")]

    print(f"📋 目標：{len(targets)} 間酒吧")
    print(f"   預計費用：約 ${len(targets) * 0.006:.2f} USD（2 calls / 間）\n")

    ok = fail = 0
    for i, bar in enumerate(targets, 1):
        pid  = bar["google_place_id"]
        name = bar.get("name", pid)
        print(f"[{i:4d}/{len(targets)}] {name[:32]:<32}", end=" ", flush=True)

        # 中文優先 → 英文補充
        raw_zh = fetch_reviews_lang(pid, "zh-TW")
        time.sleep(DELAY)
        raw_en = fetch_reviews_lang(pid, "en")
        time.sleep(DELAY)

        zh = process_raw_reviews(raw_zh)
        en = process_raw_reviews(raw_en)
        merged = merge_and_sort(zh, en)

        if merged:
            bar["review_list"] = merged
            print(f"✓ {len(merged):2d} 則  "
                  f"(zh:{len(zh)} en:{len(en)})")
            ok += 1
        else:
            bar["review_list"] = []
            print("— 無評論")
            fail += 1

        # 每 50 筆存一次
        if i % 50 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n   💾 已儲存進度（{i}/{len(targets)}）\n")

    # 最終儲存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total = sum(len(b.get("review_list", [])) for b in bars)
    print(f"\n✅ 完成！成功 {ok} 間，無評論 {fail} 間")
    print(f"   評論總則數：{total}")
    print(f"   輸出：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()
