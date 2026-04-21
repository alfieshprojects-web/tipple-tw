"""
TIPPLE — 評論抓取腳本 v1.0
==============================
讀取現有 bars.json，為每間酒吧從 Google Places API (New) 抓取最多 5 則評論。
只抓取評論文字，不重新抓取其他資料，節省 API 費用。

執行方式：
  python3 fetch_reviews.py

費用估算：
  每次 Place Details (Advanced) 呼叫約 $0.003 差額（reviews 欄位）
  3928 間 × $0.003 ≈ $12，加上原本 basic 費用
  建議先用 --top 500 只抓高分前 500 間

參數：
  --top N     只抓評分最高的前 N 間（預設全部）
  --min N     只抓 google_rating >= N 的酒吧（預設 4.0）
"""

import requests
import json
import time
import argparse
import sys
from datetime import datetime

# ============================================================
# ★ 在這裡填入你的 API Key ★
GOOGLE_API_KEY = "AIzaSyCpm-WmlRkoytWw7NLanyjWBZ82U-aUqqI"
# ============================================================

INPUT_FILE  = "bars.json"
OUTPUT_FILE = "bars.json"
DELAY       = 0.12   # 每次請求間隔（秒），避免超過 QPS 上限

def fetch_reviews(place_id: str) -> list:
    """呼叫 Places API (New) Place Details，取得最多 5 則評論"""
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "reviews",
        "Accept-Language": "zh-TW",   # 優先抓中文評論
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("reviews", [])
        result = []
        for r in raw[:5]:
            text = r.get("text", {}).get("text", "").strip()
            if not text:
                continue
            result.append({
                "author": r.get("authorAttribution", {}).get("displayName", "匿名"),
                "rating": r.get("rating", 0),
                "text":   text[:300],          # 最多保留 300 字
                "time":   r.get("relativePublishTimeDescription", ""),
                "lang":   r.get("text", {}).get("languageCode", ""),
            })
        return result
    except Exception as e:
        print(f"   ⚠ 抓取失敗：{e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="TIPPLE 評論抓取腳本")
    parser.add_argument("--top",  type=int, default=0,   help="只抓評分最高的前 N 間（0=全部）")
    parser.add_argument("--min",  type=float, default=4.0, help="最低 Google 評分門檻（預設 4.0）")
    parser.add_argument("--skip-existing", action="store_true", help="跳過已有評論的酒吧")
    args = parser.parse_args()

    print("🍸 TIPPLE 評論抓取腳本 v1.0")
    print(f"   輸入/輸出：{INPUT_FILE}")
    print(f"   開始時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 讀取現有資料
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    bars = data.get("bars", [])

    # 篩選目標酒吧
    targets = [b for b in bars if b.get("google_place_id") and b.get("google_rating", 0) >= args.min]
    targets.sort(key=lambda b: b.get("google_rating", 0), reverse=True)
    if args.top > 0:
        targets = targets[:args.top]
    if args.skip_existing:
        targets = [b for b in targets if not b.get("review_list")]

    print(f"📋 目標酒吧：{len(targets)} 間（評分 >= {args.min}）")
    print(f"   預計費用：約 ${len(targets) * 0.003:.2f} USD\n")

    ok = fail = skip = 0
    for i, bar in enumerate(targets, 1):
        pid  = bar["google_place_id"]
        name = bar.get("name", pid)
        print(f"[{i:4d}/{len(targets)}] {name[:30]:<30}", end=" ", flush=True)

        reviews = fetch_reviews(pid)
        if reviews:
            bar["review_list"] = reviews
            print(f"✓ {len(reviews)} 則評論")
            ok += 1
        else:
            print("— 無評論")
            fail += 1

        # 每 50 筆存一次，防止意外中斷
        if i % 50 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n   💾 已儲存進度（{i}/{len(targets)}）\n")

        time.sleep(DELAY)

    # 最終儲存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！")
    print(f"   成功：{ok} 間，無評論：{fail} 間")
    print(f"   輸出：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()
