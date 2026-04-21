"""
TIPPLE — 評論抓取腳本 v4.0
==============================
策略：
  - 目標城市：台北 / 新北 / 台中 / 台南 / 高雄
  - 每間酒吧 10 則：中文 8 則（zh-TW + zh 合併去重）+ 英文 2 則
  - 同時抓取 generativeSummary（Google AI 彙整所有評論的摘要）
  - 排序：文字長度 × 0.6 + 新舊程度 × 0.4

執行方式：
  python3 fetch_reviews.py              # 全部重抓
  python3 fetch_reviews.py --skip-existing  # 跳過已有評論的酒吧
  python3 fetch_reviews.py --min 4.2    # 只抓 4.2 分以上

費用估算：
  每間酒吧 3 次 Details call × $0.003 差額 = $0.009
  5 城市全部約 2700 間 ≈ $24
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
TARGET_AREAS = {'taipei', 'newtaipei', 'taichung', 'tainan', 'kaohsiung'}

# 每間酒吧的評論組成
MAX_ZH = 8   # 中文評論上限
MAX_EN = 2   # 英文評論上限

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

    print("🍸 TIPPLE 評論抓取腳本 v4.0")
    print(f"   目標城市：台北 / 新北 / 台中 / 台南 / 高雄")
    print(f"   評論組成：中文 {MAX_ZH} 則 + 英文 {MAX_EN} 則 = 10 則")
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
    print(f"   預計費用：約 ${len(targets) * 0.009:.1f} USD（3 calls / 間）\n")

    ok = fail = summary_count = 0
    now_ts = datetime.now(timezone.utc).timestamp()

    for i, bar in enumerate(targets, 1):
        pid  = bar["google_place_id"]
        name = bar.get("name", pid)
        print(f"[{i:4d}/{len(targets)}] {name[:32]:<32}", end=" ", flush=True)

        # zh-TW + zh → 中文評論（合併去重取前 8）
        d_zhtw = fetch_place_data(pid, "zh-TW"); time.sleep(DELAY)
        d_zh   = fetch_place_data(pid, "zh");    time.sleep(DELAY)
        zh_reviews = process_raw_reviews(d_zhtw.get("reviews", [])) \
                   + process_raw_reviews(d_zh.get("reviews", []))
        zh_final = dedup_and_sort(zh_reviews, now_ts)[:MAX_ZH]

        # en → 英文評論（取前 2）
        d_en = fetch_place_data(pid, "en"); time.sleep(DELAY)
        en_reviews = process_raw_reviews(d_en.get("reviews", []))
        en_final = dedup_and_sort(en_reviews, now_ts)[:MAX_EN]

        merged = zh_final + en_final
        summary = extract_summary([d_zhtw, d_en])

        if merged:
            bar["review_list"]    = merged
            bar["review_summary"] = summary
            ok += 1
            summary_count += (1 if summary else 0)
            print(f"✓ zh:{len(zh_final)} en:{len(en_final)}  {'📝' if summary else '  '}")
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
