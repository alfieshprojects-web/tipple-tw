"""
TIPPLE — 評論抓取腳本 v3.0
==============================
策略：
  1. 每間酒吧打三次 API（zh-TW + zh + en），最多取 15 則不重複評論。
  2. 同時抓取 Google generativeSummary（AI 彙整所有評論的摘要文字），
     這比單篇評論更能代表酒吧整體風格，用於 update_vibes 分類。
  3. 排序：文字長度 × 0.6 + 新舊程度 × 0.4

執行方式：
  python3 fetch_reviews.py              # 全部重抓
  python3 fetch_reviews.py --top 500    # 只抓前 500 間高分酒吧
  python3 fetch_reviews.py --skip-existing  # 跳過已有評論

費用估算：
  每間酒吧 3 次 Details call × $0.003 差額 = $0.009
  500 間 ≈ $4.5，全部 3773 間 ≈ $34
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
MAX_REVIEWS    = 15     # 最多保留幾則（3 語 × 5 則去重）

# 三語：繁中、簡中、英文
LANGUAGES = ["zh-TW", "zh", "en"]

def fetch_place_data(place_id: str, lang: str) -> dict:
    """呼叫 Places API (New) 抓取評論 + generativeSummary"""
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
    text_len  = len(r.get("text", ""))
    pub_ts    = r.get("_pub_ts", 0.0)
    days_old  = max(0, (now_ts - pub_ts) / 86400)
    recency   = max(0.0, 1.0 - days_old / 365)
    return text_len * 0.6 + recency * 400

def process_raw_reviews(raw_list: list) -> list:
    result = []
    for r in raw_list:
        text = (r.get("text") or {}).get("text", "").strip()
        if not text:
            continue
        pub_str = r.get("publishTime", "")
        result.append({
            "author":  r.get("authorAttribution", {}).get("displayName", "匿名"),
            "rating":  r.get("rating", 0),
            "text":    text[:600],
            "time":    r.get("relativePublishTimeDescription", ""),
            "lang":    (r.get("text") or {}).get("languageCode", ""),
            "_pub_ts": parse_publish_time(pub_str),
        })
    return result

def extract_summary(data_zh: dict, data_en: dict) -> str:
    """抽取 generativeSummary，優先繁中，退而其次英文"""
    for d in [data_zh, data_en]:
        gs = d.get("generativeSummary", {})
        # overview 或 description 欄位
        for field in ["overview", "description"]:
            text = (gs.get(field) or {}).get("text", "").strip()
            if text:
                return text
    return ""

def merge_and_sort(reviews_per_lang: list[list]) -> list:
    """合併多語評論，去重，依分數排序，取前 MAX_REVIEWS 則"""
    seen   = set()
    merged = []
    for reviews in reviews_per_lang:
        for r in reviews:
            key = r["text"][:60]
            if key not in seen:
                seen.add(key)
                merged.append(r)

    now_ts = datetime.now(timezone.utc).timestamp()
    merged.sort(key=lambda r: score_review(r, now_ts), reverse=True)

    for r in merged:
        r.pop("_pub_ts", None)

    return merged[:MAX_REVIEWS]

def main():
    parser = argparse.ArgumentParser(description="TIPPLE 評論抓取腳本 v3.0")
    parser.add_argument("--top",           type=int,   default=0,   help="只抓評分最高的前 N 間（0=全部）")
    parser.add_argument("--min",           type=float, default=4.0, help="最低 Google 評分門檻（預設 4.0）")
    parser.add_argument("--skip-existing", action="store_true",     help="跳過已有評論的酒吧")
    args = parser.parse_args()

    print("🍸 TIPPLE 評論抓取腳本 v3.0")
    print(f"   策略：zh-TW + zh + en 各 5 則 → 去重排序 → 最多 {MAX_REVIEWS} 則")
    print(f"   generativeSummary：✓（Google AI 彙整全部評論摘要）")
    print(f"   開始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    bars = data.get("bars", [])

    targets = [b for b in bars if b.get("google_place_id") and
               b.get("google_rating", 0) >= args.min]
    targets.sort(key=lambda b: b.get("google_rating", 0), reverse=True)
    if args.top > 0:
        targets = targets[:args.top]
    if args.skip_existing:
        targets = [b for b in targets if not b.get("review_list")]

    print(f"📋 目標：{len(targets)} 間酒吧")
    print(f"   預計費用：約 ${len(targets) * 0.009:.2f} USD（3 calls / 間）\n")

    ok = fail = summary_count = 0

    for i, bar in enumerate(targets, 1):
        pid  = bar["google_place_id"]
        name = bar.get("name", pid)
        print(f"[{i:4d}/{len(targets)}] {name[:32]:<32}", end=" ", flush=True)

        # 三語抓取
        all_raw    = []
        data_by_lang = {}
        for lang in LANGUAGES:
            d = fetch_place_data(pid, lang)
            data_by_lang[lang] = d
            all_raw.append(process_raw_reviews(d.get("reviews", [])))
            time.sleep(DELAY)

        merged = merge_and_sort(all_raw)

        # generativeSummary（用繁中 + 英文）
        summary = extract_summary(
            data_by_lang.get("zh-TW", {}),
            data_by_lang.get("en", {})
        )

        if merged:
            bar["review_list"]        = merged
            bar["review_summary"]     = summary   # AI 摘要（空字串代表無）
            ok += 1
            summary_count += (1 if summary else 0)
            counts = "/".join(str(len(r)) for r in all_raw)
            print(f"✓ {len(merged):2d} 則 ({counts})  {'📝' if summary else '  '}")
        else:
            bar["review_list"]    = []
            bar["review_summary"] = ""
            fail += 1
            print("— 無評論")

        # 每 50 筆存一次
        if i % 50 == 0:
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
